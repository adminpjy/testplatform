from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AbilityRule,
    FailureAnalysis,
    FailurePattern,
    FailureSample,
    FailureSolution,
    MaintenanceResponse,
    PlatformUser,
    RuleDraft,
    RuleValidation,
)
from app.schemas.failure_workflow import FailureSolutionUpdate, RuleValidationRequest
from app.services.audit import log_audit
from app.services.failure_analysis_service import FailureAnalysisService
from app.services.human_interventions import enable_rule_draft


def get_failure_context(db: Session, failure_sample_id: int) -> dict[str, Any]:
    sample = _sample_or_error(db, failure_sample_id)
    context = FailureAnalysisService().build_evidence_package(db, sample)
    solution = _latest_solution(db, sample.id)
    validation = _latest_validation(db, solution.id) if solution else None
    response = _latest_response(db, sample.id, solution.id if solution else None)
    return {
        "failureSampleId": sample.id,
        "context": context,
        "latestAnalysis": _analysis_payload(_latest_analysis(db, sample.id)),
        "latestSolution": _solution_payload(solution),
        "latestValidation": _validation_payload(validation),
        "maintenanceResponse": _response_payload(response),
    }


def generate_failure_solution(
    db: Session,
    failure_sample_id: int,
    *,
    actor: PlatformUser | None = None,
    force: bool = False,
) -> FailureSolution:
    sample = _sample_or_error(db, failure_sample_id)
    existing = _latest_solution(db, sample.id)
    if existing is not None and not force:
        return existing

    analysis = _latest_analysis(db, sample.id)
    if analysis is None or force:
        analysis = FailureAnalysisService().analyze_failure(db, sample.id)
        sample = _sample_or_error(db, failure_sample_id)
    context = FailureAnalysisService().build_evidence_package(db, sample)
    pattern = _upsert_failure_pattern(db, sample, analysis)
    solution = FailureSolution(
        solution_code=_code("FS"),
        failure_sample_id=sample.id,
        failure_analysis_id=analysis.id,
        pattern_id=pattern.id if pattern else None,
        project_id=sample.project_id or analysis.project_id,
        case_id=sample.case_id or analysis.case_id,
        run_id=sample.run_id,
        root_cause=analysis.root_cause,
        solution_summary=_solution_summary(analysis),
        generalized_pattern_json=analysis.generalized_pattern_json or {},
        strategy_json=analysis.solution_json or {},
        suggested_rule_json=analysis.rule_draft_json or sample.suggested_rule_json or {},
        validation_plan_json=analysis.validation_plan_json or {},
        context_snapshot_json=_context_summary(context),
        llm_prompt_snapshot_json={
            "promptKey": analysis.llm_prompt_key,
            "promptVersion": analysis.llm_prompt_version,
            "model": analysis.llm_model,
            "provider": analysis.llm_provider,
        },
        llm_response_json=analysis.llm_raw_response_json or {},
        user_reply=analysis.user_reply,
        internal_notes=analysis.internal_notes,
        status="draft",
        created_by_user_id=actor.id if actor else None,
        updated_by_user_id=actor.id if actor else None,
    )
    sample.status = "solution_drafted"
    db.add(sample)
    db.add(solution)
    db.flush()
    log_audit(
        db,
        actor,
        "failure_solution_generate",
        target_type="failure_solution",
        target_id=solution.id,
        project_id=solution.project_id,
        case_id=solution.case_id,
        run_id=solution.run_id,
        detail={"failureSampleId": sample.id, "analysisId": analysis.id},
        commit=False,
    )
    db.commit()
    db.refresh(solution)
    return solution


def list_failure_solutions(db: Session, failure_sample_id: int) -> list[FailureSolution]:
    _sample_or_error(db, failure_sample_id)
    return list(
        db.scalars(
            select(FailureSolution)
            .where(FailureSolution.failure_sample_id == failure_sample_id)
            .order_by(FailureSolution.id.desc())
        ).all()
    )


def get_failure_solution(db: Session, solution_id: int) -> FailureSolution | None:
    return db.get(FailureSolution, solution_id)


def update_failure_solution(
    db: Session,
    solution_id: int,
    payload: FailureSolutionUpdate,
    *,
    actor: PlatformUser | None = None,
) -> FailureSolution:
    solution = _solution_or_error(db, solution_id)
    before = _solution_payload(solution)
    data = payload.model_dump(exclude_unset=True)
    field_map = {
        "rootCause": "root_cause",
        "solutionSummary": "solution_summary",
        "generalizedPattern": "generalized_pattern_json",
        "strategy": "strategy_json",
        "suggestedRule": "suggested_rule_json",
        "validationPlan": "validation_plan_json",
        "userReply": "user_reply",
        "internalNotes": "internal_notes",
        "status": "status",
        "adminAdjustment": "admin_adjustment_json",
    }
    for source, target in field_map.items():
        if source in data:
            setattr(solution, target, data[source])
    solution.updated_by_user_id = actor.id if actor else solution.updated_by_user_id
    if solution.status == "draft":
        solution.status = "admin_adjusted"
    db.add(solution)
    log_audit(
        db,
        actor,
        "failure_solution_update",
        target_type="failure_solution",
        target_id=solution.id,
        project_id=solution.project_id,
        case_id=solution.case_id,
        run_id=solution.run_id,
        before=before,
        after=_solution_payload(solution),
        commit=False,
    )
    db.commit()
    db.refresh(solution)
    return solution


def create_rule_draft_from_solution(
    db: Session,
    solution_id: int,
    *,
    actor: PlatformUser | None = None,
) -> RuleDraft:
    solution = _solution_or_error(db, solution_id)
    if solution.rule_draft_id:
        existing = db.get(RuleDraft, solution.rule_draft_id)
        if existing is not None:
            return existing

    draft_payload = _rule_draft_payload(solution)
    draft = RuleDraft(
        source_type="failure_solution",
        source_id=solution.id,
        rule_type=draft_payload["ruleType"],
        rule_name=draft_payload["ruleName"],
        proposed_content_json=draft_payload["content"],
        reason=draft_payload.get("reason") or solution.root_cause,
        status="pending_review",
    )
    db.add(draft)
    db.flush()
    solution.rule_draft_id = draft.id
    solution.status = "rule_draft_ready"
    db.add(solution)
    log_audit(
        db,
        actor,
        "failure_solution_rule_draft_create",
        target_type="rule_draft",
        target_id=draft.id,
        project_id=solution.project_id,
        case_id=solution.case_id,
        run_id=solution.run_id,
        detail={"solutionId": solution.id, "failureSampleId": solution.failure_sample_id},
        commit=False,
    )
    db.commit()
    db.refresh(draft)
    return draft


def validate_solution_rule(
    db: Session,
    solution_id: int,
    payload: RuleValidationRequest,
    *,
    actor: PlatformUser | None = None,
) -> RuleValidation:
    solution = _solution_or_error(db, solution_id)
    draft = create_rule_draft_from_solution(db, solution.id, actor=actor)
    sample_ids = payload.sampleIds or [solution.failure_sample_id]
    started = datetime.now(timezone.utc)
    checks = _validate_rule_against_samples(db, draft, solution, sample_ids)
    failed = [item for item in checks if not item["passed"]]
    validation = RuleValidation(
        validation_code=_code("RV"),
        solution_id=solution.id,
        rule_draft_id=draft.id,
        project_id=solution.project_id,
        case_id=solution.case_id,
        run_id=solution.run_id,
        validation_type=payload.validationType,
        sample_ids_json={"items": sample_ids},
        status="passed" if not failed else "needs_adjustment",
        passed_count=len(checks) - len(failed),
        failed_count=len(failed),
        false_positive_count=0,
        result_json={"checks": checks},
        report_json={
            "summary": "证据预验证通过。" if not failed else "证据预验证发现需要调整的规则项。",
            "note": "这是基于失败样本证据和规则结构的预验证，不代表真实浏览器回归已经通过。",
        },
        created_by_user_id=actor.id if actor else None,
        started_at=started,
        ended_at=datetime.now(timezone.utc),
    )
    solution.status = "validated" if validation.status == "passed" else "needs_adjustment"
    db.add(solution)
    db.add(validation)
    log_audit(
        db,
        actor,
        "failure_solution_validate",
        target_type="rule_validation",
        target_id=None,
        project_id=solution.project_id,
        case_id=solution.case_id,
        run_id=solution.run_id,
        result=validation.status,
        detail={"solutionId": solution.id, "ruleDraftId": draft.id, "failedChecks": failed},
        commit=False,
    )
    db.commit()
    db.refresh(validation)
    return validation


def publish_solution_rule(
    db: Session,
    solution_id: int,
    *,
    actor: PlatformUser | None = None,
) -> AbilityRule:
    solution = _solution_or_error(db, solution_id)
    draft = create_rule_draft_from_solution(db, solution.id, actor=actor)
    validation = _latest_validation(db, solution.id)
    if validation is None or validation.status != "passed":
        raise ValueError("请先完成规则预验证且结果通过后再发布。")
    rule = enable_rule_draft(db, draft_id=draft.id)
    solution.status = "published"
    validation.ability_rule_id = rule.id
    db.add(solution)
    db.add(validation)
    log_audit(
        db,
        actor,
        "failure_solution_rule_publish",
        target_type="ability_rule",
        target_id=rule.id,
        project_id=solution.project_id,
        case_id=solution.case_id,
        run_id=solution.run_id,
        detail={"solutionId": solution.id, "ruleDraftId": draft.id, "failureSampleId": solution.failure_sample_id},
        commit=False,
    )
    db.commit()
    db.refresh(rule)
    return rule


def create_maintenance_response(
    db: Session,
    solution_id: int,
    *,
    actor: PlatformUser | None = None,
) -> MaintenanceResponse:
    solution = _solution_or_error(db, solution_id)
    validation = _latest_validation(db, solution.id)
    existing = _latest_response(db, solution.failure_sample_id, solution.id)
    context = solution.context_snapshot_json or {}
    status = "resolved" if solution.status == "published" else "draft"
    validation_result = _validation_summary(validation)
    if existing is None:
        response = MaintenanceResponse(
            response_code=_code("MR"),
            failure_sample_id=solution.failure_sample_id,
            solution_id=solution.id,
            validation_id=validation.id if validation else None,
            project_id=solution.project_id,
            case_id=solution.case_id,
            run_id=solution.run_id,
            submitted_by_user_id=_submitted_by_user_id(context),
            handled_by_user_id=actor.id if actor else None,
            status=status,
            root_cause=solution.root_cause,
            fix_summary=solution.solution_summary,
            validation_result=validation_result,
            user_reply=_response_text(solution, validation_result),
            internal_notes=solution.internal_notes,
            evidence_summary_json=context,
            resolved_at=datetime.now(timezone.utc) if status == "resolved" else None,
        )
    else:
        response = existing
        response.validation_id = validation.id if validation else response.validation_id
        response.handled_by_user_id = actor.id if actor else response.handled_by_user_id
        response.status = status
        response.root_cause = solution.root_cause
        response.fix_summary = solution.solution_summary
        response.validation_result = validation_result
        response.user_reply = _response_text(solution, validation_result)
        response.internal_notes = solution.internal_notes
        response.evidence_summary_json = context
        response.resolved_at = datetime.now(timezone.utc) if status == "resolved" else response.resolved_at
    db.add(response)
    log_audit(
        db,
        actor,
        "maintenance_response_generate",
        target_type="maintenance_response",
        target_id=response.id if existing else None,
        project_id=solution.project_id,
        case_id=solution.case_id,
        run_id=solution.run_id,
        result=status,
        detail={"solutionId": solution.id, "failureSampleId": solution.failure_sample_id},
        commit=False,
    )
    db.commit()
    db.refresh(response)
    return response


def _upsert_failure_pattern(db: Session, sample: FailureSample, analysis: FailureAnalysis) -> FailurePattern:
    pattern_json = analysis.generalized_pattern_json or {}
    pattern_name = str(pattern_json.get("patternName") or pattern_json.get("pattern_name") or sample.failure_type or "同类失败模式")
    existing = db.scalars(
        select(FailurePattern).where(
            FailurePattern.failure_type == (sample.failure_type or analysis.failure_category),
            FailurePattern.pattern_name == pattern_name,
        )
    ).first()
    source_ids = _source_ids(existing.source_sample_ids_json if existing else None)
    if sample.id not in source_ids:
        source_ids.append(sample.id)
    if existing is None:
        pattern = FailurePattern(
            pattern_code=_code("FP"),
            pattern_name=pattern_name,
            failure_type=sample.failure_type or analysis.failure_category,
            generalized_description=str(pattern_json.get("description") or analysis.root_cause or ""),
            evidence_schema_json=_dict_or_items(pattern_json.get("evidenceSchema")),
            applicability_json=_dict_or_items(pattern_json.get("applicability")),
            exclusion_json=_dict_or_items(pattern_json.get("exclusions")),
            risk_level=analysis.risk_level,
            confidence=analysis.confidence,
            source_sample_ids_json={"items": source_ids},
            status="draft",
        )
        db.add(pattern)
        db.flush()
        return pattern
    existing.generalized_description = str(pattern_json.get("description") or existing.generalized_description or "")
    existing.evidence_schema_json = _dict_or_items(pattern_json.get("evidenceSchema"))
    existing.applicability_json = _dict_or_items(pattern_json.get("applicability"))
    existing.exclusion_json = _dict_or_items(pattern_json.get("exclusions"))
    existing.confidence = max(filter(None, [existing.confidence, analysis.confidence]), default=None)
    existing.source_sample_ids_json = {"items": source_ids}
    db.add(existing)
    db.flush()
    return existing


def _validate_rule_against_samples(
    db: Session,
    draft: RuleDraft,
    solution: FailureSolution,
    sample_ids: list[int],
) -> list[dict[str, Any]]:
    content = draft.proposed_content_json or {}
    checks: list[dict[str, Any]] = []
    structural_checks = [
        ("match_config", isinstance(content.get("match_config"), dict) and bool(content.get("match_config"))),
        ("action_config", isinstance(content.get("action_config"), dict) and bool(content.get("action_config"))),
        ("success_criteria", bool(content.get("success_criteria"))),
    ]
    for key, passed in structural_checks:
        checks.append(
            {
                "name": f"规则结构包含 {key}",
                "passed": bool(passed),
                "scope": "rule_structure",
                "detail": "通过" if passed else f"规则草案缺少 {key}，需要管理员补齐。",
            }
        )

    match_config = content.get("match_config") if isinstance(content.get("match_config"), dict) else {}
    configured_failure_types = _list_values(match_config.get("failureTypes") or match_config.get("failure_types"))
    for sample_id in sample_ids:
        sample = db.get(FailureSample, sample_id)
        if sample is None:
            checks.append({"name": f"失败样本 #{sample_id} 存在", "passed": False, "scope": "sample", "detail": "样本不存在。"})
            continue
        has_evidence = any(
            [
                sample.screenshot_path,
                sample.dom_snapshot_path,
                sample.accessibility_snapshot_path,
                sample.locator_debug_path,
                sample.runtime_stream_path,
                sample.evidence_json,
            ]
        )
        type_matches = not configured_failure_types or str(sample.failure_type or "") in configured_failure_types
        checks.append(
            {
                "name": f"样本 #{sample.id} 有可复核证据",
                "passed": bool(has_evidence),
                "scope": "sample_evidence",
                "detail": "通过" if has_evidence else "缺少截图、页面快照、定位调试或运行消息，建议先补采证据。",
            }
        )
        checks.append(
            {
                "name": f"样本 #{sample.id} 匹配规则失败类型",
                "passed": bool(type_matches),
                "scope": "rule_match",
                "detail": "通过" if type_matches else f"规则匹配类型 {configured_failure_types} 未覆盖 {sample.failure_type}。",
            }
        )
    if solution.solution_summary:
        checks.append({"name": "方案摘要可用于维护回复", "passed": True, "scope": "ops_reply", "detail": solution.solution_summary})
    else:
        checks.append({"name": "方案摘要可用于维护回复", "passed": False, "scope": "ops_reply", "detail": "缺少方案摘要。"})
    return checks


def _sample_or_error(db: Session, failure_sample_id: int) -> FailureSample:
    sample = db.get(FailureSample, failure_sample_id)
    if sample is None:
        raise ValueError("Failure sample not found.")
    return sample


def _solution_or_error(db: Session, solution_id: int) -> FailureSolution:
    solution = db.get(FailureSolution, solution_id)
    if solution is None:
        raise ValueError("Failure solution not found.")
    return solution


def _latest_analysis(db: Session, failure_sample_id: int) -> FailureAnalysis | None:
    return db.scalars(
        select(FailureAnalysis)
        .where(FailureAnalysis.failure_sample_id == failure_sample_id)
        .order_by(FailureAnalysis.id.desc())
    ).first()


def _latest_solution(db: Session, failure_sample_id: int) -> FailureSolution | None:
    return db.scalars(
        select(FailureSolution)
        .where(FailureSolution.failure_sample_id == failure_sample_id)
        .order_by(FailureSolution.id.desc())
    ).first()


def _latest_validation(db: Session, solution_id: int) -> RuleValidation | None:
    return db.scalars(
        select(RuleValidation)
        .where(RuleValidation.solution_id == solution_id)
        .order_by(RuleValidation.id.desc())
    ).first()


def _latest_response(db: Session, failure_sample_id: int, solution_id: int | None) -> MaintenanceResponse | None:
    stmt = select(MaintenanceResponse).where(MaintenanceResponse.failure_sample_id == failure_sample_id)
    if solution_id is not None:
        stmt = stmt.where(MaintenanceResponse.solution_id == solution_id)
    return db.scalars(stmt.order_by(MaintenanceResponse.id.desc())).first()


def _solution_summary(analysis: FailureAnalysis) -> str:
    solution = analysis.solution_json or {}
    return str(solution.get("summary") or analysis.root_cause or "已生成失败修复方案，待预验证。")


def _rule_draft_payload(solution: FailureSolution) -> dict[str, Any]:
    draft = solution.suggested_rule_json or {}
    content = draft.get("content") if isinstance(draft.get("content"), dict) else draft
    return {
        "ruleType": str(draft.get("ruleType") or draft.get("rule_type") or "recovery_policy"),
        "ruleName": str(draft.get("ruleName") or draft.get("rule_name") or "失败恢复规则草案"),
        "reason": draft.get("reason") or solution.root_cause,
        "content": content if isinstance(content, dict) else {},
    }


def _context_summary(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "opsContext": context.get("opsContext"),
        "project": context.get("project"),
        "case": context.get("case"),
        "run": context.get("run"),
        "campaign": context.get("campaign"),
        "operator": context.get("operator"),
        "failedStep": context.get("failedStep"),
        "failureSample": context.get("failureSample"),
        "artifacts": context.get("artifacts"),
        "packageSummary": {
            "hasDomSnapshot": bool(context.get("domSnapshot")),
            "hasAccessibilitySnapshot": bool(context.get("accessibilitySnapshot")),
            "hasRuntimeMessages": bool(context.get("runtimeMessages") or context.get("runtimeStream")),
            "hasLocatorDebug": bool(context.get("locatorDebug")),
            "hasExecutionTrace": bool(context.get("executionTrace")),
            "playwrightTracePath": context.get("playwrightTracePath"),
        },
    }


def _response_text(solution: FailureSolution, validation_result: str) -> str:
    base = solution.user_reply or ""
    if base.strip():
        return f"{base.strip()}\n验证结果：{validation_result}"
    return (
        f"问题原因：{solution.root_cause or '失败原因待补充'}\n"
        f"处理方案：{solution.solution_summary or '已生成规则草案并完成预验证。'}\n"
        f"验证结果：{validation_result}"
    )


def _validation_summary(validation: RuleValidation | None) -> str:
    if validation is None:
        return "尚未完成规则预验证。"
    report = validation.report_json or {}
    return str(report.get("summary") or validation.status)


def _submitted_by_user_id(context: dict[str, Any]) -> int | None:
    operator = (context.get("operator") or {}) if isinstance(context, dict) else {}
    try:
        value = operator.get("id")
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _analysis_payload(analysis: FailureAnalysis | None) -> dict[str, Any] | None:
    if analysis is None:
        return None
    return {
        "id": analysis.id,
        "status": analysis.analysis_status,
        "failureCategory": analysis.failure_category,
        "rootCause": analysis.root_cause,
        "confidence": analysis.confidence,
        "riskLevel": analysis.risk_level,
        "requiresHumanReview": analysis.requires_human_review,
        "generalizedPattern": analysis.generalized_pattern_json,
        "solution": analysis.solution_json,
        "ruleDraft": analysis.rule_draft_json,
        "validationPlan": analysis.validation_plan_json,
        "userReply": analysis.user_reply,
        "internalNotes": analysis.internal_notes,
        "createdAt": str(analysis.created_at),
    }


def _solution_payload(solution: FailureSolution | None) -> dict[str, Any] | None:
    if solution is None:
        return None
    return {
        "id": solution.id,
        "solutionCode": solution.solution_code,
        "failureSampleId": solution.failure_sample_id,
        "failureAnalysisId": solution.failure_analysis_id,
        "patternId": solution.pattern_id,
        "projectId": solution.project_id,
        "caseId": solution.case_id,
        "runId": solution.run_id,
        "ruleDraftId": solution.rule_draft_id,
        "rootCause": solution.root_cause,
        "solutionSummary": solution.solution_summary,
        "generalizedPattern": solution.generalized_pattern_json,
        "strategy": solution.strategy_json,
        "suggestedRule": solution.suggested_rule_json,
        "validationPlan": solution.validation_plan_json,
        "contextSnapshot": solution.context_snapshot_json,
        "userReply": solution.user_reply,
        "internalNotes": solution.internal_notes,
        "status": solution.status,
        "createdAt": str(solution.created_at),
        "updatedAt": str(solution.updated_at),
    }


def _validation_payload(validation: RuleValidation | None) -> dict[str, Any] | None:
    if validation is None:
        return None
    return {
        "id": validation.id,
        "validationCode": validation.validation_code,
        "solutionId": validation.solution_id,
        "ruleDraftId": validation.rule_draft_id,
        "abilityRuleId": validation.ability_rule_id,
        "status": validation.status,
        "validationType": validation.validation_type,
        "passedCount": validation.passed_count,
        "failedCount": validation.failed_count,
        "result": validation.result_json,
        "report": validation.report_json,
        "createdAt": str(validation.created_at),
    }


def _response_payload(response: MaintenanceResponse | None) -> dict[str, Any] | None:
    if response is None:
        return None
    return {
        "id": response.id,
        "responseCode": response.response_code,
        "status": response.status,
        "rootCause": response.root_cause,
        "fixSummary": response.fix_summary,
        "validationResult": response.validation_result,
        "userReply": response.user_reply,
        "internalNotes": response.internal_notes,
        "createdAt": str(response.created_at),
        "resolvedAt": str(response.resolved_at) if response.resolved_at else None,
    }


def _source_ids(value: dict[str, Any] | None) -> list[int]:
    items = (value or {}).get("items") if isinstance(value, dict) else []
    result: list[int] = []
    if isinstance(items, list):
        for item in items:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
    return result


def _dict_or_items(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"items": value}
    if value is None:
        return {}
    return {"value": value}


def _list_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _code(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8].upper()}"


def _safe_code_part(value: str | None) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "UNKNOWN")).strip("-")
    return (text or "UNKNOWN")[:24].upper()
