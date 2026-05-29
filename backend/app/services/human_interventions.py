from datetime import datetime, timezone
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.json_utils import parse_json_object, to_compact_json
from app.llm.provider import LLMRequest, get_llm_provider
from app.models import AbilityRule, FailureSample, HumanIntervention, RuleDraft, RuntimeMessage, TestRun, TestStepRun
from app.schemas.test_runs import HumanInterventionCreate, InterventionPlan
from app.services.llm_call_logs import log_llm_call
from app.services.llm_settings import get_active_llm_config
from app.services.prompt_manager import get_prompt_manager


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
    plan = _build_intervention_plan(db, payload.user_instruction, run=run, step=step)
    intervention = HumanIntervention(
        run_id=run.id,
        step_id=step.id,
        user_instruction=payload.user_instruction,
        llm_plan_json=plan.model_dump(),
        status="analyzed",
    )
    db.add(intervention)
    db.flush()
    _mark_failure_sample(db, run.id, step.id, "intervention_created")
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
    run = _get_run_or_error(db, run_id)
    existing_result = intervention.execution_result_json or {}
    if intervention.status == "succeeded" and existing_result.get("recoveryRunId"):
        return intervention
    if run.status == "running":
        raise ValueError("当前运行仍在执行中，请等待运行失败或结束后再执行人工介入。")
    plan = InterventionPlan.model_validate(intervention.llm_plan_json or {})
    _validate_intervention_plan(plan)
    intervention.status = "executing"
    db.add(intervention)
    _add_runtime_message(
        db,
        run_id,
        "progress",
        "human_intervention",
        "正在执行人工介入方案",
        {"intervention_id": intervention.id, "actions": [step.action for step in plan.steps]},
    )
    db.commit()

    action_results = [_execute_plan_step_summary(step) for step in plan.steps]
    recovery_run = None
    recovery_error = None
    try:
        recovery_run = _start_recovery_run(db, run_id=run_id, intervention=intervention, plan=plan)
    except Exception as exc:
        recovery_error = str(exc)

    executed_at = datetime.now(timezone.utc).isoformat()
    if recovery_run is None:
        intervention.execution_result_json = {
            "status": "failed_to_start_recovery_run",
            "executedActions": action_results,
            "executedAt": executed_at,
            "message": "介入方案已通过安全校验，但未能启动恢复运行。请检查运行配置、账号和基础地址后重试。",
            "error": recovery_error,
            "resumeMode": "rerun",
        }
        intervention.status = "failed"
    else:
        intervention.execution_result_json = {
            "status": "recovery_run_started",
            "executedActions": action_results,
            "executedAt": executed_at,
            "message": f"已启动恢复运行 {recovery_run.run_code}。原运行的浏览器会话已结束，因此系统会用原测试用例和介入方案重新执行，让测试继续往下验证。",
            "recoveryRunId": recovery_run.id,
            "recoveryRunCode": recovery_run.run_code,
            "resumeMode": "rerun",
            "note": "当前架构在运行失败后会关闭浏览器会话，无法在原页面原地继续；恢复运行会把可转换的介入动作插入到失败步骤前重新执行。",
        }
        intervention.status = "succeeded"
    db.add(intervention)
    _mark_failure_sample(db, run_id, intervention.step_id, "intervention_executed" if recovery_run is not None else "intervention_failed")
    for result in action_results:
        _add_runtime_message(
            db,
            run_id,
            "progress",
            "human_intervention",
            str(result["message"]),
            {"intervention_id": intervention.id, "action": result["action"], "target": result.get("target")},
        )
    _add_runtime_message(
        db,
        run_id,
        "success" if recovery_run is not None else "error",
        "human_intervention",
        (
            f"已启动恢复运行 {recovery_run.run_code}"
            if recovery_run is not None
            else "介入方案已校验，但恢复运行启动失败"
        ),
        {
            "intervention_id": intervention.id,
            "actions": [step.action for step in plan.steps],
            "recovery_run_id": recovery_run.id if recovery_run is not None else None,
            "recovery_run_code": recovery_run.run_code if recovery_run is not None else None,
            "error": recovery_error,
        },
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


def _build_intervention_plan(db: Session, user_instruction: str, *, run: TestRun, step: TestStepRun) -> InterventionPlan:
    _validate_user_instruction(user_instruction)
    fallback = _build_rule_based_intervention_plan(user_instruction, run=run, step=step)
    llm_plan = _build_llm_intervention_plan(db, user_instruction, run=run, step=step)
    if llm_plan is not None:
        notes = list(llm_plan.safety_notes or [])
        notes.append("方案由 LLM 生成，并已通过受控动作白名单校验。")
        return InterventionPlan(summary=llm_plan.summary, steps=llm_plan.steps, safety_notes=notes)
    notes = list(fallback.safety_notes or [])
    notes.append("LLM 未配置、调用失败或输出不合规时，已使用内置安全模板生成方案。")
    return InterventionPlan(summary=fallback.summary, steps=fallback.steps, safety_notes=notes)


def _build_rule_based_intervention_plan(user_instruction: str, *, run: TestRun, step: TestStepRun) -> InterventionPlan:
    text = user_instruction.strip()
    steps: list[dict[str, Any]] = []

    if _is_auth_challenge_context(text, step):
        steps = [
            {
                "action": "wait",
                "value": "1000",
                "reason": "等待人工完成验证码、OTP 或扫码认证后的页面状态稳定。",
            },
            {
                "action": "retry_step",
                "target": str(step.step_id or step.id),
                "reason": "用户完成人工认证后继续检测登录状态，再决定是否恢复后续步骤。",
            },
        ]
        return InterventionPlan(
            summary="当前登录需要验证码或二次认证，请人工完成验证码输入或扫码认证。完成后点击继续检测登录状态。",
            steps=steps,
            safety_notes=["不会尝试识别、破解或绕过验证码；仅记录人工完成认证后的继续检测动作。"],
        )

    if "继续访问" in text:
        steps.append({"action": "click", "target": "继续访问", "reason": "用户明确要求先点击继续访问。"})
    elif "继续" in text:
        steps.append({"action": "click", "target": "继续", "reason": "用户要求继续当前流程。"})

    if "关闭" in text:
        steps.append({"action": "close_dialog", "target": "当前弹窗", "reason": "用户要求关闭干扰弹窗。"})
    if "确定" in text or "确认" in text:
        steps.append({"action": "confirm_dialog", "target": "确定", "reason": "用户要求确认当前弹窗。"})
    if "等待" in text or "稍后" in text:
        wait_ms = "8000" if ("主页面" in text or "加载完成" in text or "页面加载" in text) else "3000"
        steps.append({"action": "wait", "value": wait_ms, "reason": "用户要求等待页面加载完成后再继续。"})
    if _asks_to_retry(text):
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


def _build_llm_intervention_plan(
    db: Session,
    user_instruction: str,
    *,
    run: TestRun,
    step: TestStepRun,
) -> InterventionPlan | None:
    if not _llm_plan_generation_configured():
        return None

    started = time.monotonic()
    request: LLMRequest | None = None
    success = False
    error_summary = None
    try:
        rendered = get_prompt_manager().render_prompt(
            "human_intervention_plan",
            {
                "user_instruction": user_instruction,
                "failed_step": to_compact_json(_failed_step_payload(step)),
                "run_context": to_compact_json(_run_context_payload(db, run, step)),
            },
        )
        request = LLMRequest(
            system_prompt=rendered.system,
            user_prompt=rendered.user,
            stream=False,
            temperature=rendered.metadata.get("temperature"),
            max_tokens=rendered.metadata.get("max_tokens"),
            prompt_key=rendered.prompt_key,
            prompt_version=rendered.prompt_version,
        )
        raw = get_llm_provider().complete(request)
        payload = _normalize_llm_plan_payload(parse_json_object(raw))
        plan = InterventionPlan.model_validate(payload)
        _validate_intervention_plan(plan)
        success = True
        return plan
    except Exception as exc:
        error_summary = str(exc)
        return None
    finally:
        if request is not None:
            log_llm_call(
                run_id=run.id,
                step_id=str(step.step_id or step.id),
                prompt_key=request.prompt_key,
                prompt_version=request.prompt_version,
                success=success,
                elapsed_ms=_elapsed_ms(started),
                error_summary=error_summary,
            )


def _llm_plan_generation_configured() -> bool:
    try:
        config = get_active_llm_config()
        provider = config.provider.strip().lower()
        base_url = config.base_url
        api_key = config.api_key
    except Exception:
        provider = settings.llm_provider.strip().lower()
        base_url = settings.test_llm_base_url
        api_key = settings.test_llm_api_key.get_secret_value() if settings.test_llm_api_key else ""
    if provider in {"openai", "openai-compatible", "openai_compatible"}:
        return bool(base_url and api_key)
    return True


def _normalize_llm_plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("plan"), dict):
        payload = dict(payload["plan"])
    else:
        payload = dict(payload)
    if "steps" not in payload and isinstance(payload.get("actions"), list):
        payload["steps"] = payload["actions"]
    steps = []
    for item in payload.get("steps") or []:
        if not isinstance(item, dict):
            continue
        step = dict(item)
        if "action" not in step and "type" in step:
            step["action"] = step["type"]
        if step.get("action") == "wait" and step.get("value") is None and step.get("ms") is not None:
            step["value"] = str(step["ms"])
        steps.append(step)
    payload["summary"] = str(payload.get("summary") or "已生成受控人工介入方案。")
    payload["steps"] = steps
    payload["safety_notes"] = list(payload.get("safety_notes") or payload.get("safetyNotes") or [])
    return payload


def _failed_step_payload(step: TestStepRun) -> dict[str, Any]:
    return _sanitize_for_llm(
        {
            "id": step.id,
            "stepId": step.step_id,
            "name": step.step_name,
            "action": step.action,
            "target": step.target,
            "status": step.status,
            "locatorStrategy": step.locator_strategy,
            "elementRef": step.element_ref,
            "reason": step.reason,
            "errorSummary": step.error_summary,
            "screenshotPath": step.screenshot_path,
        }
    )


def _run_context_payload(db: Session, run: TestRun, step: TestStepRun) -> dict[str, Any]:
    sample = db.scalars(
        select(FailureSample)
        .where(FailureSample.run_id == run.id, FailureSample.step_id == step.id)
        .order_by(FailureSample.id.desc())
    ).first()
    return _sanitize_for_llm(
        {
            "runCode": run.run_code,
            "runStatus": run.status,
            "currentPhase": run.current_phase,
            "instruction": run.instruction_snapshot or run.instruction,
            "account": run.account_snapshot,
            "baseUrl": run.base_url_snapshot or run.base_url,
            "failureSample": {
                "failureType": sample.failure_type,
                "summary": sample.failure_summary,
                "aiAnalysis": sample.ai_analysis_json,
                "suggestedRule": sample.suggested_rule_json,
            }
            if sample is not None
            else None,
        }
    )


def _sanitize_for_llm(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(token in normalized for token in ["password", "secret", "token", "密码", "口令"]):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = _sanitize_for_llm(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_for_llm(item) for item in value]
    return value


def _asks_to_retry(text: str) -> bool:
    retry_words = ["重试", "再执行", "重新执行", "继续执行", "重跑", "再试", "原步骤"]
    return any(word in text for word in retry_words)


def _is_auth_challenge_context(text: str, step: TestStepRun) -> bool:
    combined = " ".join(
        [
            text,
            str(step.error_summary or ""),
            str(step.action or ""),
            str(step.target or ""),
        ]
    ).lower()
    return any(
        token in combined
        for token in [
            "login_captcha_required",
            "authentication_challenge_required",
            "protected_step_blocked_by_auth_challenge",
            "验证码",
            "校验码",
            "二次认证",
            "扫码",
            "captcha",
            "verification code",
            "otp",
            "one-time password",
            "code scanning authentication",
        ]
    )


def _execute_plan_step_summary(step) -> dict[str, Any]:
    if step.action == "wait":
        value = step.value or "3000"
        return {
            "action": step.action,
            "target": step.target,
            "value": value,
            "message": f"已校验等待页面稳定 {value} ms 的恢复动作，恢复运行会在失败步骤前执行。",
            "status": "validated",
        }
    if step.action == "retry_step":
        return {
            "action": step.action,
            "target": step.target,
            "value": step.value,
            "message": "已校验重试原失败步骤的恢复动作，恢复运行会重新执行原用例。",
            "status": "validated",
        }
    return {
        "action": step.action,
        "target": step.target,
        "value": step.value,
        "message": f"已校验人工介入动作：{step.action}，可转换的动作会插入恢复运行。",
        "status": "validated",
    }


def _start_recovery_run(
    db: Session,
    *,
    run_id: int,
    intervention: HumanIntervention,
    plan: InterventionPlan,
) -> TestRun:
    from app.services.test_run_execution import recover_test_run_from_intervention

    return recover_test_run_from_intervention(
        db,
        run_id,
        intervention_id=intervention.id,
        step_run_id=intervention.step_id,
        plan=plan.model_dump(),
    )


def _validate_user_instruction(user_instruction: str) -> None:
    normalized = user_instruction.strip().lower()
    for fragment in FORBIDDEN_INSTRUCTION_FRAGMENTS:
        if fragment in normalized:
            raise ValueError("人工介入说明包含不允许的危险操作，请只描述页面上的点击、输入、等待、关闭弹窗或重试。")


def _validate_intervention_plan(plan: InterventionPlan) -> None:
    if not plan.steps:
        raise ValueError("人工介入方案没有可执行动作，请重新生成方案。")
    for step in plan.steps:
        if step.action not in ALLOWED_INTERVENTION_ACTIONS:
            raise ValueError(f"人工介入方案包含不支持的动作：{step.action}")
        text = " ".join(str(value or "") for value in [step.target, step.value, step.reason]).lower()
        for fragment in FORBIDDEN_INSTRUCTION_FRAGMENTS:
            if fragment in text:
                raise ValueError("人工介入方案包含不允许的危险操作，请重新生成方案。")
        if step.action == "input" and _looks_like_secret_input(step.target, step.value):
            raise ValueError("人工介入方案不能保存或回放密码、口令、令牌等敏感值，请改用测试账号配置。")


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _looks_like_secret_input(target: str | None, value: str | None) -> bool:
    if value in (None, "", "***REDACTED***"):
        return False
    target_text = str(target or "").lower()
    return any(token in target_text for token in ["password", "secret", "token", "密码", "口令"])


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


def _mark_failure_sample(db: Session, run_id: int, step_id: int | None, sample_status: str) -> None:
    if step_id is None:
        return
    sample = db.scalars(
        select(FailureSample).where(FailureSample.run_id == run_id, FailureSample.step_id == step_id)
    ).first()
    if sample is not None:
        sample.status = sample_status
        db.add(sample)


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
