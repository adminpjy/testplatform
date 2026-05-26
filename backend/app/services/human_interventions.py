from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AbilityRule, FailureSample, HumanIntervention, RuleDraft, RuntimeMessage, TestRun, TestStepRun
from app.schemas.test_runs import HumanInterventionCreate, InterventionPlan


ALLOWED_INTERVENTION_ACTIONS = {
    "click",
    "input",
    "select",
    "choose_radio",
    "close_dialog",
    "confirm_dialog",
    "wait",
    "retry_step",
    "assert_text_exists",
    "assert_url_contains",
}
FORBIDDEN_INSTRUCTION_FRAGMENTS = {
    "sql",
    "select *",
    "delete from",
    "drop table",
    "insert into",
    "update ",
    "代码",
    "脚本",
    "接口",
    "api",
    "http://",
    "https://",
    "token",
}


def list_failure_samples(db: Session, *, run_id: int | None = None) -> list[FailureSample]:
    stmt = select(FailureSample)
    if run_id is not None:
        stmt = stmt.where(FailureSample.run_id == run_id)
    return list(db.scalars(stmt.order_by(FailureSample.id.desc())).all())


def list_human_interventions(db: Session, *, run_id: int | None = None) -> list[HumanIntervention]:
    stmt = select(HumanIntervention)
    if run_id is not None:
        stmt = stmt.where(HumanIntervention.run_id == run_id)
    return list(db.scalars(stmt.order_by(HumanIntervention.id.desc())).all())


def list_rule_drafts(db: Session, *, draft_status: str | None = None) -> list[RuleDraft]:
    stmt = select(RuleDraft)
    if draft_status:
        stmt = stmt.where(RuleDraft.status == draft_status)
    return list(db.scalars(stmt.order_by(RuleDraft.id.desc())).all())


def create_human_intervention(
    db: Session,
    *,
    run_id: int,
    step_id: int,
    payload: HumanInterventionCreate,
) -> HumanIntervention:
    run = _get_run_or_error(db, run_id)
    step = _get_step_or_error(db, run_id, step_id)
    plan = _build_intervention_plan(payload.user_instruction, run=run, step=step)
    intervention = HumanIntervention(
        run_id=run.id,
        step_id=step.id,
        user_instruction=payload.user_instruction,
        llm_plan_json=plan.model_dump(),
        status="analyzed",
    )
    db.add(intervention)
    db.flush()
    _add_runtime_message(
        db,
        run.id,
        "text",
        "human_intervention",
        "已生成人工介入方案",
        {"intervention_id": intervention.id, "step_id": step.id},
    )
    db.commit()
    db.refresh(intervention)
    return intervention


def execute_human_intervention(db: Session, *, run_id: int, intervention_id: int) -> HumanIntervention:
    intervention = _get_intervention_or_error(db, run_id, intervention_id)
    plan = InterventionPlan.model_validate(intervention.llm_plan_json or {})
    _validate_intervention_plan(plan)
    intervention.execution_result_json = {
        "status": "succeeded",
        "executedActions": [step.model_dump() for step in plan.steps],
        "note": "人工介入方案已通过安全校验并记录，原失败步骤可在后续运行中重试。",
    }
    intervention.status = "succeeded"
    db.add(intervention)
    _add_runtime_message(
        db,
        run_id,
        "success",
        "human_intervention",
        "人工介入方案已执行",
        {"intervention_id": intervention.id, "actions": [step.action for step in plan.steps]},
    )
    db.commit()
    db.refresh(intervention)
    return intervention


def convert_intervention_to_rule_draft(db: Session, *, run_id: int, intervention_id: int) -> RuleDraft:
    intervention = _get_intervention_or_error(db, run_id, intervention_id)
    if intervention.status != "succeeded":
        raise ValueError("Human intervention must be executed before converting to a rule draft.")

    existing = db.scalars(
        select(RuleDraft).where(
            RuleDraft.source_type == "human_intervention",
            RuleDraft.source_id == intervention.id,
        )
    ).first()
    if existing is not None:
        return existing

    plan = InterventionPlan.model_validate(intervention.llm_plan_json or {})
    draft = RuleDraft(
        source_type="human_intervention",
        source_id=intervention.id,
        rule_type="recovery_policy",
        rule_name=_rule_draft_name(intervention),
        proposed_content_json={
            "rule_code_suggestion": f"HUMAN-RECOVERY-{intervention.id}-v1",
            "match_config": {
                "run_id": run_id,
                "step_id": intervention.step_id,
                "user_instruction": intervention.user_instruction,
            },
            "action_config": {
                "intervention_plan": plan.model_dump(),
            },
            "success_criteria": ["人工介入动作完成", "原失败步骤可重试"],
            "risk_policy": {
                "allowed_actions": sorted(ALLOWED_INTERVENTION_ACTIONS),
                "blocked_operation_categories": [
                    "database_mutation",
                    "external_service_call",
                    "custom_runtime_execution",
                ],
            },
        },
        reason="由成功的人工介入记录生成，待人工审核后启用。",
        status="pending_review",
    )
    db.add(draft)
    _add_runtime_message(
        db,
        run_id,
        "success",
        "rule_draft",
        "已生成人工介入规则草案",
        {"intervention_id": intervention.id},
    )
    db.commit()
    db.refresh(draft)
    return draft


def enable_rule_draft(db: Session, *, draft_id: int) -> AbilityRule:
    draft = db.get(RuleDraft, draft_id)
    if draft is None:
        raise ValueError("Rule draft not found.")
    content = draft.proposed_content_json or {}
    rule_code = str(content.get("rule_code_suggestion") or f"HUMAN-RECOVERY-{draft.id}-v1")
    existing_rule = db.scalars(select(AbilityRule).where(AbilityRule.rule_code == rule_code)).first()
    if existing_rule is not None:
        draft.status = "active"
        db.add(draft)
        db.commit()
        return existing_rule

    rule = AbilityRule(
        rule_code=rule_code,
        rule_name=draft.rule_name,
        rule_type=draft.rule_type,
        intent=draft.reason,
        status="active",
        priority=300,
        match_config_json=(content.get("match_config") if isinstance(content, dict) else {}) or {},
        action_config_json=(content.get("action_config") if isinstance(content, dict) else {}) or {},
        success_criteria_json={"criteria": content.get("success_criteria", [])},
        fallback_strategies_json={"source": "human_intervention"},
        risk_level="medium",
        confidence_threshold=0.75,
        source=f"rule_draft:{draft.id}",
        production_enabled=True,
    )
    draft.status = "active"
    db.add(rule)
    db.add(draft)
    db.commit()
    db.refresh(rule)
    return rule


def _build_intervention_plan(user_instruction: str, *, run: TestRun, step: TestStepRun) -> InterventionPlan:
    _validate_user_instruction(user_instruction)
    text = user_instruction.strip()
    steps: list[dict[str, Any]] = []

    if "继续访问" in text:
        steps.append({"action": "click", "target": "继续访问", "reason": "用户明确要求先点击继续访问。"})
    elif "继续" in text:
        steps.append({"action": "click", "target": "继续", "reason": "用户要求继续当前流程。"})

    if "关闭" in text:
        steps.append({"action": "close_dialog", "target": "当前弹窗", "reason": "用户要求关闭干扰弹窗。"})
    if "确定" in text or "确认" in text:
        steps.append({"action": "confirm_dialog", "target": "确定", "reason": "用户要求确认当前弹窗。"})
    if "等待" in text or "稍后" in text:
        steps.append({"action": "wait", "value": "1000", "reason": "用户要求等待页面稳定。"})
    if "重试" in text:
        steps.append({"action": "retry_step", "target": str(step.step_id or step.id), "reason": "用户要求重试原步骤。"})
    if "验证" in text and "文本" in text:
        steps.append({"action": "assert_text_exists", "target": step.target or "", "reason": "用户要求验证页面文本。"})

    if not steps:
        steps = [
            {"action": "wait", "value": "1000", "reason": "默认等待页面稳定。"},
            {"action": "retry_step", "target": str(step.step_id or step.id), "reason": "默认重试原失败步骤。"},
        ]

    return InterventionPlan(
        summary=f"针对运行 {run.run_code} 的失败步骤生成介入计划。",
        steps=steps,
        safety_notes=["仅允许受控 UI 动作，已拒绝危险操作。"],
    )


def _validate_user_instruction(user_instruction: str) -> None:
    normalized = user_instruction.strip().lower()
    for fragment in FORBIDDEN_INSTRUCTION_FRAGMENTS:
        if fragment in normalized:
            raise ValueError("Human intervention instruction contains a forbidden operation.")


def _validate_intervention_plan(plan: InterventionPlan) -> None:
    for step in plan.steps:
        if step.action not in ALLOWED_INTERVENTION_ACTIONS:
            raise ValueError(f"Unsupported intervention action: {step.action}")
        text = " ".join(str(value or "") for value in [step.target, step.value, step.reason]).lower()
        for fragment in FORBIDDEN_INSTRUCTION_FRAGMENTS:
            if fragment in text:
                raise ValueError("Intervention plan contains a forbidden operation.")


def _get_run_or_error(db: Session, run_id: int) -> TestRun:
    run = db.get(TestRun, run_id)
    if run is None:
        raise ValueError("Test run not found.")
    return run


def _get_step_or_error(db: Session, run_id: int, step_id: int) -> TestStepRun:
    step = db.get(TestStepRun, step_id)
    if step is None or step.run_id != run_id:
        raise ValueError("Test step not found.")
    return step


def _get_intervention_or_error(db: Session, run_id: int, intervention_id: int) -> HumanIntervention:
    intervention = db.get(HumanIntervention, intervention_id)
    if intervention is None or intervention.run_id != run_id:
        raise ValueError("Human intervention not found.")
    return intervention


def _rule_draft_name(intervention: HumanIntervention) -> str:
    instruction = " ".join(str(intervention.user_instruction or "").split())
    return f"人工介入恢复策略：{instruction[:40] or intervention.id}"


def _add_runtime_message(
    db: Session,
    run_id: int,
    message_type: str,
    phase: str,
    content: str,
    metadata: dict[str, Any],
) -> None:
    db.add(
        RuntimeMessage(
            run_id=run_id,
            type=message_type,
            phase=phase,
            content=content,
            method="human_intervention",
            metadata_json=metadata,
        )
    )
