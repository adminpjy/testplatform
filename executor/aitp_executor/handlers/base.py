import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HandlerContext:
    step: dict[str, Any]
    dsl: dict[str, Any] = field(default_factory=dict)
    execution_context: dict[str, Any] = field(default_factory=dict)

    @property
    def step_id(self) -> Any:
        return self.execution_context.get("step_id") or self.step.get("id") or self.step.get("step_id")

    @property
    def step_number(self) -> Any:
        return self.execution_context.get("step_number")

    @property
    def intent(self) -> str:
        operation_intent = self.step.get("operationIntent") or {}
        return str(operation_intent.get("intent") or "")


class RuntimeAbilityResolver:
    """Consumes pre-resolved AbilityResolver output and falls back to builtin rules."""

    def resolve(self, ctx: HandlerContext, *, intent: str, rule_types: list[str]) -> dict[str, Any]:
        resolution = ctx.step.get("abilityResolution") or ctx.execution_context.get("ability_resolution") or {}
        if resolution.get("matchedRules") or resolution.get("selectedRules"):
            return resolution
        backend_resolution = self._resolve_from_backend(intent=intent, rule_types=rule_types, ctx=ctx)
        if backend_resolution:
            return backend_resolution
        return {"matchedRules": [], "selectedRules": [], "reason": "未找到能力规则。", "source": "none"}

    def _resolve_from_backend(self, *, intent: str, rule_types: list[str], ctx: HandlerContext) -> dict[str, Any] | None:
        try:
            backend_dir = Path(__file__).resolve().parents[3] / "backend"
            if backend_dir.exists() and str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            from app.services.ability_resolver import resolve_abilities

            return resolve_abilities(
                None,
                {
                    "intent": intent,
                    "ruleTypes": rule_types,
                    "pageContext": {"step": redact_sensitive(ctx.step)},
                    "environment": str((ctx.dsl.get("environment") or "test")),
                },
            )
        except Exception:
            return None


class CommonOperationHandler:
    handler_name = "common_operation_handler"
    rule_types: list[str] = []
    default_intent = "unknown"

    def __init__(self, *, ability_resolver: RuntimeAbilityResolver | None = None) -> None:
        self.ability_resolver = ability_resolver or RuntimeAbilityResolver()

    def context(
        self,
        step: dict[str, Any] | None,
        dsl: dict[str, Any] | None,
        execution_context: dict[str, Any] | None,
    ) -> HandlerContext:
        return HandlerContext(step=step or {}, dsl=dsl or {}, execution_context=execution_context or {})

    def resolve_rules(self, ctx: HandlerContext, *, intent: str | None = None, rule_types: list[str] | None = None) -> dict[str, Any]:
        return self.ability_resolver.resolve(ctx, intent=intent or ctx.intent or self.default_intent, rule_types=rule_types or self.rule_types)

    def emit(
        self,
        ctx: HandlerContext,
        message_type: str,
        phase: str,
        content: str,
        method: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        emitter = ctx.execution_context.get("emit_runtime")
        if not emitter:
            return
        payload = {"handler": self.handler_name, "step_id": ctx.step_id, **(metadata or {})}
        emitter(message_type, phase, content, method or self.handler_name, payload)

    def debug(self, ctx: HandlerContext, event: dict[str, Any]) -> None:
        writer = ctx.execution_context.get("append_debug")
        if not writer:
            return
        writer(
            {
                "phase": "handler_decision",
                "handler": self.handler_name,
                "stepId": ctx.step_id,
                **event,
            }
        )

    def emit_rule_hits(self, ctx: HandlerContext, resolution: dict[str, Any]) -> None:
        selected = resolution.get("selectedRules") or []
        self.debug(
            ctx,
            {
                "phase": "handler_ability_resolve",
                "intent": ctx.intent or self.default_intent,
                "matchedRules": [rule.get("rule_code") for rule in resolution.get("matchedRules") or [] if rule.get("rule_code")],
                "selectedRules": [rule.get("rule_code") for rule in selected if rule.get("rule_code")],
                "source": resolution.get("source"),
                "reason": resolution.get("reason"),
            },
        )
        for rule in selected[:3]:
            code = rule.get("rule_code")
            name = rule.get("rule_name") or code
            self.emit(
                ctx,
                "success",
                "ability_resolve",
                str(rule.get("runtimeMessage") or f"命中规则 {code}：将按{name}处理。"),
                "ability_resolver",
                {"rule_code": code, "rule_type": rule.get("rule_type"), "rule_name": name},
            )


def handler_outcome(strategy: str, element_ref: Any, confidence: float, reason: Any, **extra: Any) -> dict[str, Any]:
    payload = {
        "locator_strategy": strategy,
        "element_ref": str(element_ref) if element_ref is not None else None,
        "confidence": confidence,
        "reason": reason if isinstance(reason, str) else json_dumps(reason),
        "needs_vision_fallback": False,
        "fallback_reason": None,
        "candidates": [],
    }
    payload.update(extra)
    return payload


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if re.search(r"(password|secret|token|authorization|密码|口令)", str(key), re.IGNORECASE):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def require_locator(result: Any) -> Any:
    if getattr(result, "locator", None) is None:
        raise RuntimeError(getattr(result, "fallback_reason", None) or getattr(result, "reason", "locator_not_found"))
    return result.locator


def locator_outcome(result: Any, **extra: Any) -> dict[str, Any]:
    payload = handler_outcome(
        getattr(result, "strategy", "locator"),
        getattr(result, "element_ref", None),
        getattr(result, "confidence", 0.5),
        getattr(result, "reason", ""),
        needs_vision_fallback=getattr(result, "needs_vision_fallback", False),
        fallback_reason=getattr(result, "fallback_reason", None),
        candidates=getattr(result, "candidates", []),
    )
    payload.update(extra)
    return payload


def path_segments(value: Any) -> list[str]:
    if isinstance(value, list):
        cleaned_items = [clean_segment(str(item), index) for index, item in enumerate(value) if clean_segment(str(item), index)]
        if len(cleaned_items) == 1:
            return _path_segments_from_text(cleaned_items[0]) or cleaned_items
        flattened: list[str] = []
        for item in cleaned_items:
            nested = _path_segments_from_text(item)
            flattened.extend(nested or [item])
        return _normalize_portal_path_segments(flattened)
    return _path_segments_from_text(str(value or ""))


def _path_segments_from_text(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text or "://" in text or not re.search(r"[/>\-→\\]", text):
        return []
    if re.search(r"[/>\u2192\\]", text):
        return _normalize_portal_path_segments(
            [
                cleaned
                for index, segment in enumerate(re.split(r"\s*(?:/|>|→|\\)\s*", text))
                if (cleaned := clean_segment(segment, index))
            ]
        )
    if "-" in text:
        return _normalize_portal_path_segments(
            [
                cleaned
                for index, segment in enumerate(re.split(r"\s*-\s*", text))
                if (cleaned := clean_segment(segment, index))
            ]
        )
    return []


def _normalize_portal_path_segments(segments: list[str]) -> list[str]:
    if len(segments) < 3 or segments[0] != "系统导航":
        return segments
    category_index = 1
    for index, segment in enumerate(segments[1:4], start=1):
        if re.sub(r"\s*[（(]\d+[）)]\s*$", "", segment).strip() in {
            "我的应用",
            "办公自动化",
            "财务",
            "财务管理",
            "生产",
            "生产经营",
            "设备",
            "设备管理",
            "采购",
            "采购管理",
            "销售",
            "销售管理",
            "安环",
            "安全环保",
            "综合",
            "综合管理",
            "人力资源",
            "信息化",
        }:
            category_index = index
            break
    app_name = "-".join(segments[category_index + 1 :]).strip()
    if not app_name:
        return segments
    return [segments[0], segments[category_index], app_name]


def clean_segment(segment: str, index: int) -> str:
    cleaned = segment.strip().strip("“”\"'，,。；;：:")
    if index == 0:
        cleaned = re.sub(r"^(进入|打开|点击|导航到|访问|前往|切换到|跳转到)", "", cleaned).strip()
    return cleaned


def is_visible_enabled(locator: Any) -> bool:
    try:
        return locator.is_visible(timeout=500) and locator.is_enabled(timeout=500)
    except Exception:
        return False
