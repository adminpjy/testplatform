from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.abilities.base_pack import BASE_ABILITY_RULES
from app.models import AbilityRule, FailureSample
from app.schemas.abilities import AbilityRuleCreate, AbilityRuleUpdate


def ensure_base_ability_rules(db: Session) -> None:
    existing_rules = {rule.rule_code: rule for rule in db.scalars(select(AbilityRule)).all()}
    for rule_data in BASE_ABILITY_RULES:
        existing = existing_rules.get(rule_data["rule_code"])
        if existing is not None:
            _backfill_missing_rule_fields(existing, rule_data)
            db.add(existing)
            continue
        db.add(AbilityRule(**rule_data))
    db.commit()


def _backfill_missing_rule_fields(rule: AbilityRule, rule_data: dict[str, Any]) -> None:
    """Keep operator-maintained rule content intact while adding missing built-in metadata.

    Built-in seed data is a bootstrap template. Once a rule exists in the database,
    the database version is the source of truth for production behavior.
    """

    for field_name, value in rule_data.items():
        current = getattr(rule, field_name, None)
        if current in (None, "", [], {}):
            setattr(rule, field_name, value)
    if rule.status == "archived":
        rule.production_enabled = False


def list_rules(
    db: Session,
    *,
    rule_type: str | None = None,
    rule_status: str | None = None,
    production_enabled: bool | None = None,
) -> list[AbilityRule]:
    stmt = select(AbilityRule)
    if rule_type:
        stmt = stmt.where(AbilityRule.rule_type == rule_type)
    if rule_status:
        stmt = stmt.where(AbilityRule.status == rule_status)
    else:
        stmt = stmt.where(AbilityRule.status != "archived")
    if production_enabled is not None:
        stmt = stmt.where(AbilityRule.production_enabled == production_enabled)
    stmt = stmt.order_by(AbilityRule.rule_type, AbilityRule.priority, AbilityRule.id)
    return list(db.scalars(stmt).all())


def get_rule(db: Session, rule_id: int) -> AbilityRule | None:
    return db.get(AbilityRule, rule_id)


def create_rule(db: Session, payload: AbilityRuleCreate) -> AbilityRule:
    rule = AbilityRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, rule: AbilityRule, payload: AbilityRuleUpdate) -> AbilityRule:
    update_data: dict[str, Any] = payload.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(rule, field_name, value)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def set_rule_enabled(db: Session, rule: AbilityRule, enabled: bool) -> AbilityRule:
    rule.production_enabled = enabled
    rule.status = "active" if enabled else "disabled"
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def validate_rule_config(db: Session, rule: AbilityRule, *, sample_ids: list[int] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    match_config = rule.match_config_json or {}
    action_config = rule.action_config_json or {}
    success_config = rule.success_criteria_json or {}
    fallback_config = rule.fallback_strategies_json or {}

    checks.append(_check("规则包含匹配条件", bool(match_config), "rule_structure", "match_config_json"))
    checks.append(_check("规则包含动作配置", bool(action_config), "rule_structure", "action_config_json"))
    checks.append(_check("规则包含成功标准", bool(success_config), "rule_structure", "success_criteria_json"))
    checks.append(
        _check(
            "执行器支持该规则类型",
            rule.rule_type in _SUPPORTED_EXECUTABLE_RULE_TYPES,
            "executor_support",
            f"当前支持：{', '.join(sorted(_SUPPORTED_EXECUTABLE_RULE_TYPES))}",
        )
    )
    checks.extend(_executable_config_checks(rule.rule_type, action_config, success_config, fallback_config))

    for sample_id in sample_ids or []:
        sample = db.get(FailureSample, sample_id)
        if sample is None:
            checks.append(_check(f"失败样本 #{sample_id} 存在", False, "sample", "样本不存在。"))
            continue
        evidence = _sample_evidence_text(sample)
        checks.append(_check(f"失败样本 #{sample.id} 有证据", bool(evidence.strip()), "sample_evidence", "截图/DOM/可访问性/日志证据"))
        checks.extend(_evidence_match_checks(rule, sample, evidence))

    failed = [item for item in checks if not item["passed"]]
    return {
        "ruleId": rule.id,
        "ruleCode": rule.rule_code,
        "status": "passed" if not failed else "needs_adjustment",
        "passedCount": len(checks) - len(failed),
        "failedCount": len(failed),
        "checks": checks,
        "summary": "规则预验证通过，可进入试运行。" if not failed else "规则预验证发现缺口，请调整后再发布或试运行。",
    }


_SUPPORTED_EXECUTABLE_RULE_TYPES = {
    "table_row_action",
    "approval_workflow",
    "form_fill",
    "navigation",
    "query",
    "dialog_selector",
}


def _executable_config_checks(
    rule_type: str,
    action_config: dict[str, Any],
    success_config: dict[str, Any],
    fallback_config: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if rule_type == "table_row_action":
        checks.append(
            _check(
                "表格行规则配置了行入口",
                bool(_list_value(action_config, "rowLinkSelectors", "entrySelectors", "rowEntryLabels")),
                "executor_config",
                "需要配置行入口 selector 或入口文字。",
            )
        )
        checks.append(
            _check(
                "表格行规则配置了打开成功标识",
                bool(_list_value(action_config, "openSuccessTexts", "openSuccessSelectors") or _list_value(success_config, "texts", "selectors", "criteria")),
                "executor_config",
                "需要配置进入详情后的文字或 selector。",
            )
        )
        checks.append(
            _check(
                "表格行规则配置了失败恢复策略",
                bool(_list_value(action_config, "clickStrategies") or _list_value(fallback_config, "strategies")),
                "executor_config",
                "建议至少配置 click/dblclick/js_click 或 fallback 策略。",
            )
        )
    elif rule_type == "approval_workflow":
        checks.append(
            _check(
                "审批规则配置了入口或表单就绪标识",
                bool(_list_value(action_config, "entryLabels", "entrySelectors", "formReadyTexts", "formReadySelectors")),
                "executor_config",
                "需要能识别审批入口或审批表单。",
            )
        )
        checks.append(
            _check(
                "审批规则配置了提交按钮",
                bool(_list_value(action_config, "submitLabels", "submitSelectors")),
                "executor_config",
                "需要配置提交/审核/审批按钮。",
            )
        )
    else:
        checks.append(_check("规则类型已注册为可执行类型", True, "executor_config", rule_type))
    return checks


def _evidence_match_checks(rule: AbilityRule, sample: FailureSample, evidence: str) -> list[dict[str, Any]]:
    action_config = rule.action_config_json or {}
    match_config = rule.match_config_json or {}
    success_config = rule.success_criteria_json or {}
    checks: list[dict[str, Any]] = []
    context_signals = _list_value(match_config, "contextSignals", "page_signals", "trigger_phrases")
    if context_signals:
        hits = [item for item in context_signals if item in evidence]
        checks.append(
            _check(
                f"样本 #{sample.id} 命中适用页面/上下文",
                bool(hits),
                "rule_match",
                "命中：" + "、".join(hits[:6]) if hits else "样本证据未出现规则上下文信号。",
            )
        )
    selectors = _list_value(action_config, "tableRowSelector", "rowLinkSelectors", "entrySelectors", "openSuccessSelectors", "formReadySelectors", "submitSelectors")
    if selectors:
        selector_hits = [selector for selector in selectors if _selector_hint_in_evidence(selector, evidence)]
        checks.append(
            _check(
                f"样本 #{sample.id} 证据包含规则 selector 线索",
                bool(selector_hits),
                "selector_evidence",
                "命中：" + "、".join(selector_hits[:6]) if selector_hits else "未在 DOM/可访问性证据中找到 selector 线索。",
            )
        )
    success_texts = _list_value(action_config, "openSuccessTexts", "formReadyTexts") + _list_value(success_config, "texts", "pageSignals", "criteria")
    if success_texts:
        hits = [item for item in success_texts if item in evidence]
        checks.append(
            _check(
                f"样本 #{sample.id} 可验证成功标识",
                True,
                "success_evidence",
                "当前失败样本通常可能不包含详情成功标识；命中：" + "、".join(hits[:6]) if hits else "失败样本未出现成功标识，预验证将要求真实试运行确认。",
            )
        )
    return checks


def _sample_evidence_text(sample: FailureSample) -> str:
    parts = [sample.failure_summary or ""]
    for path in [
        sample.dom_snapshot_path,
        sample.accessibility_snapshot_path,
        sample.locator_debug_path,
        sample.runtime_stream_path,
        sample.execution_trace_path,
    ]:
        if not path:
            continue
        try:
            from executor.aitp_executor.utils.file_paths import resolve_project_path

            resolved = resolve_project_path(path)
            if resolved.exists():
                parts.append(resolved.read_text(encoding="utf-8", errors="ignore")[:200_000])
        except Exception:
            continue
    if isinstance(sample.evidence_json, dict):
        parts.append(str(sample.evidence_json))
    return "\n".join(parts)


def _selector_hint_in_evidence(selector: str, evidence: str) -> bool:
    text = str(selector or "").strip()
    if not text:
        return False
    tokens = [
        token.strip(" .#>:[()]'\"")
        for token in text.replace("'", " ").replace('"', " ").replace(">", " ").replace(":", " ").split()
    ]
    tokens = [token for token in tokens if len(token) >= 3 and token not in {"has-text", "nth-child", "tbody", "button"}]
    return any(token in evidence for token in tokens)


def _list_value(mapping: dict[str, Any], *keys: str) -> list[str]:
    result: list[str] = []
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, list):
            result.extend(str(item).strip() for item in value if str(item).strip())
        elif value not in (None, ""):
            result.append(str(value).strip())
    return result


def _check(name: str, passed: bool, scope: str, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "scope": scope, "detail": detail}
