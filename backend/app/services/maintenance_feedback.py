from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FailureAnalysis, FailureSample, MaintenanceFeedback, TestCase, TestProject, TestRun
from app.schemas.enterprise import MaintenanceFeedbackCreate
from app.services.test_run_execution import list_artifacts, list_step_runs


def create_maintenance_feedback(db: Session, payload: MaintenanceFeedbackCreate) -> MaintenanceFeedback:
    if payload.runId is None and payload.failureSampleId is None:
        raise ValueError("runId or failureSampleId is required.")
    sample = db.get(FailureSample, payload.failureSampleId) if payload.failureSampleId else None
    if payload.failureSampleId and sample is None:
        raise ValueError("Failure sample not found.")
    run_id = payload.runId or (sample.run_id if sample else None)
    run = db.get(TestRun, run_id) if run_id else None
    if run is None:
        raise ValueError("Test run not found.")
    package = _evidence_package(db, run, sample, payload)
    feedback = MaintenanceFeedback(
        feedback_code=_feedback_code(),
        project_id=run.project_id,
        case_id=run.case_id,
        run_id=run.id,
        failure_sample_id=sample.id if sample else None,
        status="submitted",
        summary=payload.summary or package["summary"],
        evidence_package_json=_safe_json(package),
        artifact_paths_json=_artifact_paths(package),
        maintainer_notes=payload.userNote,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def get_maintenance_feedback(db: Session, feedback_id: int) -> MaintenanceFeedback | None:
    return db.get(MaintenanceFeedback, feedback_id)


def list_maintenance_feedback(db: Session, project_id: int | None = None) -> list[MaintenanceFeedback]:
    query = select(MaintenanceFeedback)
    if project_id is not None:
        query = query.where(MaintenanceFeedback.project_id == project_id)
    return list(db.scalars(query.order_by(MaintenanceFeedback.id.desc())).all())


def _evidence_package(
    db: Session,
    run: TestRun,
    sample: FailureSample | None,
    payload: MaintenanceFeedbackCreate,
) -> dict[str, Any]:
    project = db.get(TestProject, run.project_id) if run.project_id else None
    case = db.get(TestCase, run.case_id) if run.case_id else None
    steps = list_step_runs(db, run.id)
    artifacts = list_artifacts(db, run.id)
    failure_samples = _failure_samples_for_run(db, run.id, sample)
    analyses = _failure_analyses_for_run(db, run.id)
    summary = _feedback_summary(run, sample, case)
    return {
        "summary": summary,
        "userNote": payload.userNote,
        "project": {
            "id": project.id if project else None,
            "projectCode": project.project_code if project else None,
            "projectName": (project.project_name or project.name) if project else None,
            "systemName": project.system_name if project else None,
            "baseUrl": project.base_url if project else None,
            "loginUrl": project.login_url if project else None,
            "homeUrl": project.home_url if project else None,
        },
        "case": {
            "id": case.id if case else None,
            "caseCode": case.case_code if case else None,
            "caseName": case.case_name if case else None,
            "naturalLanguageGoal": case.natural_language_goal if case else None,
            "menuPath": case.menu_path if case else None,
            "businessIntent": case.business_intent if case else None,
        },
        "run": {
            "id": run.id,
            "runCode": run.run_code,
            "status": run.status,
            "currentPhase": run.current_phase,
            "errorSummary": run.error_summary,
            "instruction": run.instruction_snapshot or run.instruction,
            "baseUrl": run.base_url_snapshot or run.base_url,
            "durationMs": run.duration_ms,
            "createdAt": str(run.created_at),
            "startedAt": str(run.started_at) if run.started_at else None,
            "endedAt": str(run.ended_at) if run.ended_at else None,
        },
        "dslSnapshot": run.dsl_snapshot or run.dsl_json,
        "testDataSnapshot": run.test_data_snapshot,
        "settingsSnapshot": run.settings_snapshot,
        "accountSnapshot": run.account_snapshot,
        "steps": [
            {
                "id": step.id,
                "stepId": step.step_id,
                "stepName": step.step_name,
                "action": step.action,
                "target": step.target,
                "status": step.status,
                "locatorStrategy": step.locator_strategy,
                "confidence": step.confidence,
                "reason": step.reason,
                "screenshotPath": step.screenshot_path,
                "errorSummary": step.error_summary,
            }
            for step in steps
        ],
        "artifacts": [
            {
                "id": artifact.id,
                "stepId": artifact.step_id,
                "type": artifact.artifact_type,
                "path": artifact.file_path,
                "metadata": artifact.metadata_json,
            }
            for artifact in artifacts
        ],
        "failureSamples": [
            {
                "id": item.id,
                "stepId": item.step_id,
                "failureType": item.failure_type,
                "failureSummary": item.failure_summary,
                "screenshotPath": item.screenshot_path,
                "aiAnalysis": item.ai_analysis_json,
                "suggestedRule": item.suggested_rule_json,
            }
            for item in failure_samples
        ],
        "failureAnalyses": [
            {
                "id": analysis.id,
                "failureSampleId": analysis.failure_sample_id,
                "status": analysis.analysis_status,
                "category": analysis.failure_category,
                "rootCause": analysis.root_cause,
                "confidence": analysis.confidence,
                "suggestions": analysis.suggestions_json,
                "recommendedActions": analysis.recommended_actions_json,
                "errorSummary": analysis.error_summary,
            }
            for analysis in analyses
        ],
    }


def _failure_samples_for_run(db: Session, run_id: int, preferred: FailureSample | None) -> list[FailureSample]:
    items = list(db.scalars(select(FailureSample).where(FailureSample.run_id == run_id).order_by(FailureSample.id)).all())
    if preferred and all(item.id != preferred.id for item in items):
        items.append(preferred)
    return items


def _failure_analyses_for_run(db: Session, run_id: int) -> list[FailureAnalysis]:
    return list(db.scalars(select(FailureAnalysis).where(FailureAnalysis.run_id == run_id).order_by(FailureAnalysis.id)).all())


def _artifact_paths(package: dict[str, Any]) -> dict[str, Any]:
    by_type: dict[str, list[str]] = {}
    for artifact in package.get("artifacts") or []:
        artifact_type = str(artifact.get("type") or "unknown")
        path = artifact.get("path")
        if path:
            by_type.setdefault(artifact_type, []).append(path)
    return by_type


def _feedback_summary(run: TestRun, sample: FailureSample | None, case: TestCase | None) -> str:
    case_name = case.case_name if case else f"run {run.run_code}"
    if sample is not None:
        return f"{case_name} 执行失败：{sample.failure_summary or sample.failure_type or run.error_summary or '未识别失败原因'}"
    if run.error_summary:
        return f"{case_name} 执行异常：{run.error_summary}"
    return f"{case_name} 需要维护人员复核运行记录 {run.run_code}。"


def _safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in ["password", "token", "secret", "api_key", "apikey", "密码", "口令", "密钥"]):
                result[key] = "***REDACTED***"
            else:
                result[key] = _safe_json(item)
        return result
    if isinstance(value, list):
        return [_safe_json(item) for item in value]
    return value


def _feedback_code() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"FB-{stamp}-{uuid4().hex[:6].upper()}"

