from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AbilityKnowledge, PrescanSession, RuleDraft, TestCase, TestProject
from app.schemas.enterprise import PrescanRequest, PrescanResponse
from app.services.dsl_post_processor import parse_menu_path


def run_project_prescan(db: Session, project_id: int, payload: PrescanRequest) -> PrescanResponse:
    project = db.get(TestProject, project_id)
    if project is None or project.deleted_at is not None or project.status == "deleted":
        raise ValueError("Project not found.")
    cases = _selected_cases(db, project_id, payload.caseIds)
    started_at = _utc_now()
    session = PrescanSession(
        project_id=project_id,
        session_code=_session_code(),
        status="running",
        mode=payload.mode,
        dry_run=payload.dryRun,
        case_ids_json={"items": [case.id for case in cases]},
        started_at=started_at,
    )
    db.add(session)
    db.flush()

    plan_items: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    enhanced_cases: list[dict[str, Any]] = []
    rule_draft_ids: list[int] = []
    knowledge_ids: list[int] = []
    for case in cases:
        case_plan = _case_prescan_plan(case)
        plan_items.append(case_plan)
        findings.extend(case_plan["findings"])
        enhanced_cases.append(_enhanced_case_suggestion(case, case_plan))
        for rule in _rule_drafts_from_case(session.id, case, case_plan):
            db.add(rule)
            db.flush()
            rule_draft_ids.append(rule.id)
        for knowledge in _knowledge_from_case(project_id, case, case_plan):
            db.add(knowledge)
            db.flush()
            knowledge_ids.append(knowledge.id)

    session.status = "completed"
    session.plan_json = {"items": plan_items}
    session.findings_json = {"items": findings}
    session.rule_draft_ids_json = {"items": rule_draft_ids}
    session.ability_knowledge_ids_json = {"items": knowledge_ids}
    session.enhanced_cases_json = {"items": enhanced_cases}
    session.ended_at = _utc_now()
    db.add(session)
    db.commit()
    db.refresh(session)
    return PrescanResponse(
        session=session,
        summary={
            "caseCount": len(cases),
            "ruleDraftCount": len(rule_draft_ids),
            "abilityKnowledgeCount": len(knowledge_ids),
            "dryRun": payload.dryRun,
            "message": "已基于初始用例生成预扫计划和规则草案，未执行真实提交类操作。",
        },
        ruleDraftIds=rule_draft_ids,
        abilityKnowledgeIds=knowledge_ids,
        enhancedCases=enhanced_cases,
    )


def get_prescan_session(db: Session, session_id: int) -> PrescanSession | None:
    return db.get(PrescanSession, session_id)


def _selected_cases(db: Session, project_id: int, case_ids: list[int] | None) -> list[TestCase]:
    query = select(TestCase).where(
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
        TestCase.status != "deleted",
    )
    if case_ids:
        query = query.where(TestCase.id.in_(case_ids))
    return list(db.scalars(query.order_by(TestCase.id)).all())


def _case_prescan_plan(case: TestCase) -> dict[str, Any]:
    goal = case.natural_language_goal or case.instruction or case.case_name
    menu_path = case.menu_path or _dsl_menu_path(case.dsl_json)
    steps = [
        {"type": "login", "goal": "进入统一身份认证并登录", "risk": "low"},
    ]
    findings: list[dict[str, Any]] = []
    if menu_path:
        segments = parse_menu_path(menu_path)
        steps.append({"type": "navigation", "target": menu_path, "segments": segments, "risk": "low"})
        findings.append({"type": "navigation_path", "target": menu_path, "segments": segments})
    if _looks_like_table_case(goal):
        steps.append({"type": "table_scan", "target": "业务列表", "risk": "low"})
        findings.append({"type": "table_rule_needed", "reason": "用例包含列表、待办、查询或逐行处理语义。"})
    if _looks_like_form_case(goal):
        steps.append({"type": "form_scan", "target": "业务表单", "risk": "medium"})
        findings.append({"type": "form_rule_needed", "reason": "用例包含新增、修改、填写或保存语义。"})
    if _looks_like_approval_case(goal):
        steps.append({"type": "approval_panel_scan", "target": "审批操作区", "risk": "high", "dryRunOnly": True})
        findings.append({"type": "approval_rule_needed", "reason": "用例包含审批、意见、提交、同意或驳回语义。"})
    steps.append({"type": "assertion_scan", "target": "成功证据", "risk": "low"})
    return {"caseId": case.id, "caseName": case.case_name, "goal": goal, "menuPath": menu_path, "steps": steps, "findings": findings}


def _rule_drafts_from_case(session_id: int, case: TestCase, plan: dict[str, Any]) -> list[RuleDraft]:
    drafts: list[RuleDraft] = []
    goal = str(plan.get("goal") or "")
    menu_path = plan.get("menuPath")
    if menu_path:
        drafts.append(
            RuleDraft(
                source_type="prescan_session",
                source_id=session_id,
                rule_type="navigation_rule",
                rule_name=f"{case.case_name} 菜单路径规则",
                proposed_content_json={
                    "caseId": case.id,
                    "menuPath": menu_path,
                    "pathSegments": parse_menu_path(str(menu_path)),
                    "evidenceRequired": ["menu selected state", "right panel content changed", "url/title/breadcrumb changed"],
                },
                reason="用例包含菜单路径，预扫生成导航规则草案。",
                status="pending_review",
            )
        )
    if _looks_like_table_case(goal):
        drafts.append(
            RuleDraft(
                source_type="prescan_session",
                source_id=session_id,
                rule_type="table_rule",
                rule_name=f"{case.case_name} 列表处理规则",
                proposed_content_json={
                    "caseId": case.id,
                    "targets": ["待办列表", "查询结果列表", "业务表格"],
                    "rowOpenPolicy": ["new_page", "same_page", "dialog"],
                    "loopPolicy": {"source": "visible_rows", "returnToList": True},
                },
                reason="用例包含列表或逐行处理语义，需要沉淀表格行打开和返回规则。",
                status="pending_review",
            )
        )
    if _looks_like_form_case(goal):
        drafts.append(
            RuleDraft(
                source_type="prescan_session",
                source_id=session_id,
                rule_type="form_rule",
                rule_name=f"{case.case_name} 表单字段规则",
                proposed_content_json={
                    "caseId": case.id,
                    "fieldDiscovery": ["label", "placeholder", "aria-label", "table header", "nearby text"],
                    "dataPolicy": "generate_valid_data_when_missing",
                    "negativeCases": "derive_from_required_fields_and_format_errors",
                },
                reason="用例需要填写表单，预扫生成字段识别和数据生成规则草案。",
                status="pending_review",
            )
        )
    if _looks_like_approval_case(goal):
        drafts.append(
            RuleDraft(
                source_type="prescan_session",
                source_id=session_id,
                rule_type="approval_rule",
                rule_name=f"{case.case_name} 审批操作规则",
                proposed_content_json={
                    "caseId": case.id,
                    "opinionFields": ["我的意见", "审批意见", "意见", "处理意见"],
                    "defaultOpinion": "按要求执行",
                    "submitButtons": ["提交", "审批", "同意", "通过", "办理"],
                    "nextHandlerPolicy": "keep_existing_when_present",
                    "riskLevel": "high",
                    "requiresSuccessEvidence": True,
                },
                reason="用例包含审批语义，高风险动作只生成规则草案并要求审核。",
                status="pending_review",
            )
        )
    return drafts


def _knowledge_from_case(project_id: int, case: TestCase, plan: dict[str, Any]) -> list[AbilityKnowledge]:
    semantic_target = case.menu_path or case.business_intent or case.case_name
    return [
        AbilityKnowledge(
            knowledge_type="prescan_case_profile",
            project_id=project_id,
            page_url_pattern=None,
            page_fingerprint=None,
            semantic_target=semantic_target,
            business_intent=plan.get("goal"),
            action_path_json={"steps": plan.get("steps") or []},
            evidence_json={"source": "prescan", "caseId": case.id, "findings": plan.get("findings") or []},
            confidence=0.65,
            status="active",
        )
    ]


def _enhanced_case_suggestion(case: TestCase, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "caseId": case.id,
        "caseName": case.case_name,
        "suggestions": [
            "补充页面成功证据，避免只用固定文字判断。",
            "缺少测试数据时由 LLM 根据页面字段生成正例、反例和边界值。",
            "高风险提交类动作需保留过程截图和明确成功提示。",
        ],
        "plan": plan,
    }


def _dsl_menu_path(dsl: dict | None) -> str | None:
    if not isinstance(dsl, dict):
        return None
    for step in dsl.get("steps") or []:
        if isinstance(step, dict) and step.get("action") == "navigate_path" and step.get("target"):
            return str(step["target"])
    return None


def _looks_like_table_case(text: str) -> bool:
    return any(token in text for token in ["列表", "待办", "表格", "查询", "逐一", "每一行", "第一行", "结果"])


def _looks_like_form_case(text: str) -> bool:
    return any(token in text for token in ["填写", "输入", "新增", "修改", "保存", "上传", "选择"])


def _looks_like_approval_case(text: str) -> bool:
    return any(token in text for token in ["审批", "意见", "提交", "同意", "驳回", "传阅", "办理"])


def _session_code() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"PRESCAN-{stamp}-{uuid4().hex[:6].upper()}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

