from __future__ import annotations

from typing import Any

from executor.aitp_executor.handlers.base import HandlerContext


def merged_rule_config(ctx: HandlerContext, *, rule_type: str | None = None) -> dict[str, Any]:
    """Return executable config merged from selected ability rules.

    Earlier selected rules have higher precedence. This keeps project-specific
    or preferred rules from being overwritten by generic fallback rules.
    """

    selected = selected_rules(ctx, rule_type=rule_type)
    merged: dict[str, Any] = {"match": {}, "action": {}, "success": {}, "fallback": {}, "rules": []}
    for rule in reversed(selected):
        merged["rules"].append(rule_summary(rule))
        _merge_dict(merged["match"], rule.get("matchConfig") or rule.get("match_config") or {})
        _merge_dict(merged["action"], rule.get("actionConfig") or rule.get("action_config") or {})
        _merge_dict(merged["success"], rule.get("successCriteria") or rule.get("success_criteria") or {})
        _merge_dict(merged["fallback"], rule.get("fallbackStrategies") or rule.get("fallback_strategies") or {})
    merged["rules"].reverse()
    return merged


def selected_rules(ctx: HandlerContext, *, rule_type: str | None = None) -> list[dict[str, Any]]:
    resolution = ctx.step.get("abilityResolution") or ctx.execution_context.get("ability_resolution") or {}
    rules = resolution.get("selectedRules") or []
    if not isinstance(rules, list):
        return []
    result = [rule for rule in rules if isinstance(rule, dict)]
    if rule_type:
        result = [rule for rule in result if str(rule.get("rule_type") or rule.get("ruleType") or "") == rule_type]
    return result


def rule_summary(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_code": rule.get("rule_code") or rule.get("ruleCode"),
        "rule_name": rule.get("rule_name") or rule.get("ruleName"),
        "rule_type": rule.get("rule_type") or rule.get("ruleType"),
        "score": rule.get("score"),
    }


def list_setting(*values: Any) -> list[str]:
    for value in values:
        result = _list(value)
        if result:
            return result
    return []


def int_setting(*values: Any, default: int, minimum: int, maximum: int) -> int:
    for value in values:
        if value in (None, ""):
            continue
        try:
            parsed = int(float(str(value).strip()))
        except (TypeError, ValueError):
            continue
        return max(minimum, min(parsed, maximum))
    return default


def _merge_dict(base: dict[str, Any], incoming: dict[str, Any]) -> None:
    if not isinstance(incoming, dict):
        return
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            nested = dict(base[key])
            _merge_dict(nested, value)
            base[key] = nested
            continue
        base[key] = value


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value).strip()]
