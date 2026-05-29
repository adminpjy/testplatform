from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.abilities.base_pack import BASE_ABILITY_RULES
from app.models import AbilityRule
from app.services.operation_intent_classifier import OperationIntentClassifier


@dataclass
class AbilityResolveRequest:
    intent: str
    ruleTypes: list[str] = field(default_factory=list)
    systemId: int | None = None
    projectId: int | None = None
    pageContext: dict[str, Any] = field(default_factory=dict)
    environment: str = "test"


class AbilityResolver:
    def resolve(self, db: Session | None, request: AbilityResolveRequest | dict[str, Any]) -> dict[str, Any]:
        payload = _request_from_any(request)
        source = "database"
        rules = self._load_database_rules(db, payload) if db is not None else []
        if not rules:
            source = "builtin"
            rules = self._load_builtin_rules(payload)

        scored = []
        for rule in rules:
            score, reasons = _score_rule(rule, payload)
            if score <= 0:
                continue
            scored.append((score, int(rule.get("priority") or 100), rule))
            rule["_score"] = round(score, 4)
            rule["_reason"] = "；".join(reasons) if reasons else "规则类型匹配。"

        scored.sort(key=lambda item: (-item[0], item[1], str(item[2].get("rule_code") or "")))
        matched = [_public_rule(rule) for _, _, rule in scored[:12]]
        selected = _select_rules(payload.intent, matched)
        reason = (
            "；".join(f"命中规则 {rule['rule_code']}" for rule in selected)
            if selected
            else "未命中可用能力规则。"
        )
        return {
            "matchedRules": matched,
            "selectedRules": selected,
            "reason": reason,
            "source": source,
        }

    def _load_database_rules(self, db: Session, payload: AbilityResolveRequest) -> list[dict[str, Any]]:
        stmt = select(AbilityRule).where(AbilityRule.status == "active")
        if _is_production(payload.environment):
            stmt = stmt.where(AbilityRule.production_enabled.is_(True))
        if payload.ruleTypes:
            stmt = stmt.where(AbilityRule.rule_type.in_(payload.ruleTypes))
        rows = list(db.scalars(stmt).all())
        return [_rule_to_dict(row) for row in rows if _scope_matches(row, payload)]

    def _load_builtin_rules(self, payload: AbilityResolveRequest) -> list[dict[str, Any]]:
        rules = []
        for rule in BASE_ABILITY_RULES:
            if rule.get("status") != "active":
                continue
            if _is_production(payload.environment) and not rule.get("production_enabled"):
                continue
            if payload.ruleTypes and rule.get("rule_type") not in payload.ruleTypes:
                continue
            rules.append(dict(rule))
        return rules


def resolve_abilities(db: Session | None, payload: AbilityResolveRequest | dict[str, Any]) -> dict[str, Any]:
    return AbilityResolver().resolve(db, payload)


def annotate_dsl_with_abilities(
    db: Session | None,
    dsl: dict[str, Any],
    *,
    instruction: str | None = None,
    project_id: int | None = None,
    system_id: int | None = None,
    environment: str = "test",
) -> dict[str, Any]:
    classifier = OperationIntentClassifier()
    resolver = AbilityResolver()
    annotated = dict(dsl)
    steps = []
    for step in annotated.get("steps") or []:
        if not isinstance(step, dict):
            continue
        current = dict(step)
        classification = classifier.classify(
            action=current.get("action"),
            target=current.get("target"),
            stepName=current.get("name") or current.get("step_name"),
            instruction=instruction,
            context=current,
        )
        rule_types = _rule_types_for_intent(classification.intent, str(current.get("action") or ""))
        resolution = resolver.resolve(
            db,
            AbilityResolveRequest(
                intent=classification.intent,
                ruleTypes=rule_types,
                systemId=system_id,
                projectId=project_id,
                pageContext={"step": current, "instruction": instruction or ""},
                environment=environment,
            ),
        )
        current["operationIntent"] = classification.model_dump()
        current["abilityResolution"] = resolution
        current["ruleHints"] = [rule["rule_code"] for rule in resolution.get("selectedRules") or []]
        steps.append(current)
    annotated["steps"] = steps
    return annotated


def _request_from_any(value: AbilityResolveRequest | dict[str, Any]) -> AbilityResolveRequest:
    if isinstance(value, AbilityResolveRequest):
        return value
    return AbilityResolveRequest(
        intent=str(value.get("intent") or ""),
        ruleTypes=[str(item) for item in value.get("ruleTypes") or value.get("rule_types") or []],
        systemId=value.get("systemId") or value.get("system_id"),
        projectId=value.get("projectId") or value.get("project_id"),
        pageContext=dict(value.get("pageContext") or value.get("page_context") or {}),
        environment=str(value.get("environment") or "test"),
    )


def _rule_types_for_intent(intent: str, action: str) -> list[str]:
    mapping = {
        "login": ["login", "global_interruption", "risk_policy"],
        "navigate_path": ["navigation"],
        "enter_page": ["navigation"],
        "query_list": ["query", "table_detection"],
        "open_table_row": ["table_row_action", "table_detection"],
        "process_table_rows": ["table_row_action", "table_detection"],
        "click_table_row_action": ["table_row_action", "candidate_ranking"],
        "create_record": ["create", "form_fill", "form_control"],
        "update_record": ["update", "form_fill", "form_control"],
        "delete_record": ["delete", "risk_policy"],
        "view_detail": ["detail_navigation", "table_row_action"],
        "view_flow": ["approval_workflow"],
        "submit_for_approval": ["approval_workflow"],
        "approval_pass": ["approval_workflow"],
        "approval_reject": ["approval_workflow"],
        "fill_form": ["form_fill", "form_control", "dropdown", "date_picker", "org_selector", "person_selector", "tree_selector", "dialog_selector", "file_upload"],
        "fill_field": ["form_fill", "form_control", "candidate_ranking"],
        "select_dropdown": ["dropdown", "form_control"],
        "select_date": ["date_picker", "form_control"],
        "select_date_range": ["date_picker", "form_control"],
        "select_org": ["org_selector", "tree_selector", "dialog_selector"],
        "select_person": ["person_selector", "tree_selector", "dialog_selector"],
        "select_tree_node": ["tree_selector"],
        "select_from_dialog": ["dialog_selector"],
        "upload_file": ["file_upload"],
        "handle_dialog": ["global_interruption", "dialog_handler", "recovery_policy"],
        "assert_result": ["assertion"],
    }
    if action == "business_goal" and intent == "unknown":
        return ["navigation", "approval_workflow", "query", "create", "update", "delete", "detail_navigation"]
    return mapping.get(intent, [])


def _score_rule(rule: dict[str, Any], payload: AbilityResolveRequest) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    rule_type = str(rule.get("rule_type") or "")
    if payload.ruleTypes and rule_type in payload.ruleTypes:
        score += 0.25
        reasons.append("规则类型匹配")
    intent = str(rule.get("intent") or "")
    if _intent_matches(intent, payload.intent):
        score += 0.45
        reasons.append("操作意图匹配")
    preferred = _preferred_codes(payload.intent)
    if rule.get("rule_code") in preferred:
        score += 0.35
        reasons.append("优先规则匹配")
    context_text = _flatten(payload.pageContext)
    match_config = rule.get("match_config_json") or {}
    hits = _match_hits(match_config, context_text)
    if hits:
        score += min(0.2, len(hits) * 0.04)
        reasons.append("上下文命中：" + "、".join(hits[:4]))
    if not payload.ruleTypes and not payload.intent:
        score += 0.05
    return min(score, 1.0), reasons


def _preferred_codes(intent: str) -> set[str]:
    return {
        "login": {"LOGIN-USERNAME-PASSWORD-v1", "LOGIN-SUCCESS-DETECT-v1", "LOGIN-CAPTCHA-DETECT-v1", "LOGIN-RETRY-RISK-v1"},
        "navigate_path": {"NAV-MENU-PATH-v1", "NAV-EXPAND-PARENT-v1", "NAV-ALREADY-ON-TARGET-v1"},
        "enter_page": {"NAV-MENU-PATH-v1", "NAV-DASHBOARD-CARD-v1", "NAV-MENU-SEARCH-v1"},
        "approval_pass": {"APPROVAL-PASS-v1", "APPROVAL-FILL-OPINION-v1", "APPROVAL-CONFIRM-v1"},
        "approval_reject": {"APPROVAL-REJECT-v1", "APPROVAL-FILL-OPINION-v1", "APPROVAL-CONFIRM-v1"},
        "view_flow": {"APPROVAL-VIEW-FLOW-v1", "APPROVAL-VIEW-RECORD-v1"},
        "fill_form": {"FORM-FILL-TEXT-v1", "FORM-FILL-REQUIRED-v1", "FORM-FILL-DEFAULT-DATA-v1"},
        "fill_field": {"FORM-FILL-TEXT-v1", "FORM-FILL-LABEL-NEARBY-v1", "CANDIDATE-RANK-FORM-FIELD-v1"},
        "select_dropdown": {"DROPDOWN-CUSTOM-SELECT-v1", "DROPDOWN-NATIVE-SELECT-v1", "DROPDOWN-DEFAULT-OPTION-v1"},
        "select_org": {"ORG-REQUIRE-CLARIFICATION-v1", "ORG-TREE-SELECT-v1", "ORG-MODAL-SELECT-v1"},
        "select_person": {"PERSON-APPROVER-CLARIFY-v1", "PERSON-MODAL-SELECT-v1", "PERSON-CURRENT-USER-v1"},
        "process_table_rows": {"ROW-OPEN-TODO-v1", "ROW-SKIP-NON-PROCESSABLE-v1", "TABLE-DATA-ROW-v1"},
        "click_table_row_action": {"ROW-CLICK-ACTION-v1", "ROW-MORE-ACTIONS-v1", "CANDIDATE-RANK-BUSINESS-ACTION-v1"},
        "query_list": {"QUERY-KEYWORD-v1", "QUERY-RESULT-REFRESH-v1", "TABLE-DETECT-BASIC-v1"},
        "assert_result": {"ASSERT-MULTI-EVIDENCE-v1", "ASSERT-TOAST-SUCCESS-v1"},
    }.get(intent, set())


def _select_rules(intent: str, matched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not matched:
        return []
    preferred = _preferred_codes(intent)
    selected = [rule for rule in matched if rule["rule_code"] in preferred]
    if selected:
        return selected[:5]
    top_score = matched[0].get("score") or 0
    return [rule for rule in matched if (rule.get("score") or 0) >= max(0.5, top_score - 0.12)][:5]


def _scope_matches(rule: AbilityRule, payload: AbilityResolveRequest) -> bool:
    match_config = rule.match_config_json or {}
    project_scope = match_config.get("project_id") or match_config.get("projectId")
    system_scope = match_config.get("system_id") or match_config.get("systemId")
    if project_scope is not None and payload.projectId is not None and int(project_scope) != int(payload.projectId):
        return False
    if system_scope is not None and payload.systemId is not None and int(system_scope) != int(payload.systemId):
        return False
    return True


def _rule_to_dict(rule: AbilityRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "rule_code": rule.rule_code,
        "rule_name": rule.rule_name,
        "rule_type": rule.rule_type,
        "intent": rule.intent,
        "status": rule.status,
        "priority": rule.priority,
        "match_config_json": rule.match_config_json,
        "action_config_json": rule.action_config_json,
        "success_criteria_json": rule.success_criteria_json,
        "fallback_strategies_json": rule.fallback_strategies_json,
        "failure_patterns_json": rule.failure_patterns_json,
        "recovery_strategies_json": rule.recovery_strategies_json,
        "risk_level": rule.risk_level,
        "confidence_threshold": rule.confidence_threshold,
        "production_enabled": rule.production_enabled,
        "source": rule.source,
        "version": rule.version,
    }


def _public_rule(rule: dict[str, Any]) -> dict[str, Any]:
    action_config = rule.get("action_config_json") or {}
    runtime_message = action_config.get("runtime_message") or action_config.get("runtime_message_template")
    if not runtime_message:
        runtime_message = f"命中规则 {rule.get('rule_code')}：将按{rule.get('rule_name')}处理。"
    return {
        "id": rule.get("id"),
        "rule_code": rule.get("rule_code"),
        "rule_name": rule.get("rule_name"),
        "rule_type": rule.get("rule_type"),
        "intent": rule.get("intent"),
        "priority": rule.get("priority"),
        "risk_level": rule.get("risk_level"),
        "version": rule.get("version") or "1.0.0",
        "score": rule.get("_score", 0),
        "reason": rule.get("_reason", ""),
        "runtimeMessage": runtime_message,
        "failurePatterns": (rule.get("failure_patterns_json") or {}).get("patterns", []),
        "recoveryStrategies": (rule.get("recovery_strategies_json") or {}).get("strategies", []),
    }


def _intent_matches(rule_intent: str, requested: str) -> bool:
    if not rule_intent or not requested:
        return False
    left = rule_intent.lower()
    right = requested.lower()
    aliases = {
        "username_password_login": {"login"},
        "detect_table": {"query_list"},
        "detect_data_rows": {"query_list", "process_table_rows"},
        "query_result_refresh": {"query_list"},
        "select_dropdown_option": {"select_dropdown"},
        "select_date": {"select_date", "select_date_range"},
        "select_organization": {"select_org"},
        "select_person": {"select_person"},
        "select_tree_node": {"select_tree_node", "select_org", "select_person"},
        "select_from_dialog": {"select_from_dialog", "select_org", "select_person"},
        "approval_pass": {"approval_pass"},
        "approval_reject": {"approval_reject"},
        "fill_text_field": {"fill_field", "fill_form"},
        "fill_form": {"fill_form", "fill_field"},
    }
    return left == right or left in right or right in left or right in aliases.get(left, set())


def _match_hits(match_config: dict[str, Any], text: str) -> list[str]:
    hits: list[str] = []
    for value in _iter_strings(match_config):
        if value and value.lower() in text.lower():
            hits.append(value)
    return list(dict.fromkeys(hits))


def _iter_strings(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
    elif isinstance(value, str):
        yield value


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _is_production(environment: str | None) -> bool:
    return str(environment or "").lower() in {"prod", "production"}
