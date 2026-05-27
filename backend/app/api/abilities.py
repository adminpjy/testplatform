from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AbilityKnowledge, AbilityRule, FailureSample, HumanIntervention, LLMCallLog, RuleDraft, RuntimeMessage
from app.schemas.abilities import (
    AbilityKnowledgeRead,
    AbilityRuleCreate,
    AbilityRuleRead,
    AbilityRuleUpdate,
    RuleResolverRequest,
    RuleResolverResponse,
)
from app.services.abilities import create_rule, get_rule, list_rules, set_rule_enabled, update_rule
from app.services.rule_resolver import resolve_rule

router = APIRouter()


ABILITY_CATEGORIES = [
    {"key": "login", "label": "登录", "ruleTypes": ["login"]},
    {"key": "global_interruption", "label": "弹窗 / 中断页", "ruleTypes": ["global_interruption", "dialog_handler"]},
    {"key": "navigation", "label": "导航", "ruleTypes": ["navigation"]},
    {"key": "query", "label": "查询", "ruleTypes": ["query"]},
    {"key": "table_detection", "label": "表格识别", "ruleTypes": ["table_detection"]},
    {"key": "table_row_action", "label": "表格行操作", "ruleTypes": ["table_row_action"]},
    {"key": "form_fill", "label": "表单填写", "ruleTypes": ["form_fill", "form_control"]},
    {"key": "dropdown", "label": "下拉框", "ruleTypes": ["dropdown"]},
    {"key": "date_picker", "label": "日期", "ruleTypes": ["date_picker"]},
    {"key": "org_selector", "label": "组织机构", "ruleTypes": ["org_selector"]},
    {"key": "person_selector", "label": "人员选择", "ruleTypes": ["person_selector"]},
    {"key": "tree_selector", "label": "树选择", "ruleTypes": ["tree_selector"]},
    {"key": "dialog_selector", "label": "弹窗选择", "ruleTypes": ["dialog_selector"]},
    {"key": "file_upload", "label": "文件上传", "ruleTypes": ["file_upload"]},
    {"key": "approval_workflow", "label": "审批流程", "ruleTypes": ["approval_workflow"]},
    {"key": "assertion", "label": "断言验证", "ruleTypes": ["assertion"]},
]


@router.get("/rules", response_model=list[AbilityRuleRead])
def read_rules(
    rule_type: str | None = None,
    rule_status: str | None = None,
    production_enabled: bool | None = None,
    db: Session = Depends(get_db),
) -> list[AbilityRuleRead]:
    return list_rules(
        db,
        rule_type=rule_type,
        rule_status=rule_status,
        production_enabled=production_enabled,
    )


@router.get("/stats")
def read_ability_stats(db: Session = Depends(get_db)) -> dict:
    rules = list(db.scalars(select(AbilityRule)).all())
    failures = list(db.scalars(select(FailureSample)).all())
    interventions = list(db.scalars(select(HumanIntervention)).all())
    drafts = list(db.scalars(select(RuleDraft)).all())
    runtime_messages = list(db.scalars(select(RuntimeMessage).order_by(RuntimeMessage.id.desc()).limit(2000)).all())
    llm_logs = list(db.scalars(select(LLMCallLog)).all())
    rule_type_by_code = {rule.rule_code: rule.rule_type for rule in rules}
    hit_counts_by_type: dict[str, int] = {}
    hit_counts_by_code: dict[str, int] = {}
    vision_fallback_count = 0
    llm_decision_count = len(llm_logs)
    for message in runtime_messages:
        metadata = message.metadata_json or {}
        rule_type = metadata.get("rule_type")
        rule_code = metadata.get("rule_code")
        if rule_code:
            hit_counts_by_code[str(rule_code)] = hit_counts_by_code.get(str(rule_code), 0) + 1
            rule_type = rule_type or rule_type_by_code.get(str(rule_code))
        if rule_type:
            hit_counts_by_type[str(rule_type)] = hit_counts_by_type.get(str(rule_type), 0) + 1
        content = str(message.content or "")
        method = str(message.method or "")
        phase = str(message.phase or "")
        if phase == "vision" or method == "vision_resolver" or "视觉兜底" in content:
            vision_fallback_count += 1
        if method.startswith("llm") or "llm" in method.lower() or phase.startswith("llm"):
            llm_decision_count += 1

    failure_distribution: dict[str, int] = {}
    failure_counts_by_category: dict[str, int] = {}
    for sample in failures:
        failure_type = sample.failure_type or "unknown_failure"
        failure_distribution[failure_type] = failure_distribution.get(failure_type, 0) + 1
        category = _failure_category(failure_type)
        failure_counts_by_category[category] = failure_counts_by_category.get(category, 0) + 1

    rule_type_stats: dict[str, dict] = {}
    for rule in rules:
        item = rule_type_stats.setdefault(rule.rule_type, {"total": 0, "active": 0})
        item["total"] += 1
        if rule.status == "active":
            item["active"] += 1

    overview = []
    for category in ABILITY_CATEGORIES:
        rule_types = category["ruleTypes"]
        total = sum(rule_type_stats.get(rule_type, {}).get("total", 0) for rule_type in rule_types)
        active = sum(rule_type_stats.get(rule_type, {}).get("active", 0) for rule_type in rule_types)
        hits = sum(hit_counts_by_type.get(rule_type, 0) for rule_type in rule_types)
        failures_for_category = sum(failure_counts_by_category.get(rule_type, 0) for rule_type in rule_types)
        overview.append(
            {
                **category,
                "ruleCount": total,
                "activeCount": active,
                "recentHitCount": hits,
                "recentFailureCount": failures_for_category,
            }
        )

    return {
        "operationOverview": overview,
        "ruleTypeStats": rule_type_stats,
        "ruleHitCountsByType": hit_counts_by_type,
        "ruleHitCountsByCode": hit_counts_by_code,
        "failureTypeDistribution": failure_distribution,
        "failureCountsByCategory": failure_counts_by_category,
        "humanInterventionCount": len(interventions),
        "ruleDraftCount": len(drafts),
        "visionFallbackCount": vision_fallback_count,
        "llmDecisionCount": llm_decision_count,
    }


@router.post("/rules", response_model=AbilityRuleRead, status_code=status.HTTP_201_CREATED)
def create_ability_rule(payload: AbilityRuleCreate, db: Session = Depends(get_db)) -> AbilityRuleRead:
    try:
        return create_rule(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rule code already exists.",
        ) from exc


@router.put("/rules/{rule_id}", response_model=AbilityRuleRead)
def update_ability_rule(
    rule_id: int,
    payload: AbilityRuleUpdate,
    db: Session = Depends(get_db),
) -> AbilityRuleRead:
    rule = _get_rule_or_404(db, rule_id)
    try:
        return update_rule(db, rule, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rule code already exists.",
        ) from exc


@router.post("/rules/{rule_id}/enable", response_model=AbilityRuleRead)
def enable_ability_rule(rule_id: int, db: Session = Depends(get_db)) -> AbilityRuleRead:
    return set_rule_enabled(db, _get_rule_or_404(db, rule_id), True)


@router.post("/rules/{rule_id}/disable", response_model=AbilityRuleRead)
def disable_ability_rule(rule_id: int, db: Session = Depends(get_db)) -> AbilityRuleRead:
    return set_rule_enabled(db, _get_rule_or_404(db, rule_id), False)


@router.post("/resolve", response_model=RuleResolverResponse)
def resolve_ability_rule(
    payload: RuleResolverRequest,
    db: Session = Depends(get_db),
) -> RuleResolverResponse:
    return resolve_rule(db, payload)


@router.get("/knowledge", response_model=list[AbilityKnowledgeRead])
def read_ability_knowledge(
    system_id: int | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[AbilityKnowledgeRead]:
    stmt = select(AbilityKnowledge).order_by(AbilityKnowledge.id.desc())
    if system_id is not None:
        stmt = stmt.where(AbilityKnowledge.system_id == system_id)
    if project_id is not None:
        stmt = stmt.where(AbilityKnowledge.project_id == project_id)
    return list(db.scalars(stmt).all())


def _failure_category(failure_type: str) -> str:
    if failure_type.startswith(("login_", "auth_", "authentication_", "protected_step_blocked_by_auth")):
        return "login"
    if failure_type.startswith(("menu_", "navigation_")):
        return "navigation"
    if failure_type.startswith("table_"):
        return "table_row_action"
    if failure_type.startswith("form_"):
        return "form_fill"
    if failure_type.startswith("dropdown_"):
        return "dropdown"
    if failure_type.startswith("date_"):
        return "date_picker"
    if failure_type.startswith("org_"):
        return "org_selector"
    if failure_type.startswith("person_"):
        return "person_selector"
    if failure_type.startswith(("dialog_", "confirm_", "blocking_")):
        return "dialog_selector"
    if failure_type.startswith("approval_"):
        return "approval_workflow"
    if failure_type.startswith("vision_"):
        return "vision_fallback"
    return "unknown"


def _get_rule_or_404(db: Session, rule_id: int):
    rule = get_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ability rule not found.")
    return rule
