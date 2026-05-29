from datetime import datetime, timezone
from threading import Thread
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import FailureSample, RuntimeMessage, TestArtifact, TestCase, TestProject, TestRun, TestStepRun, TestSystem
from app.schemas.test_runs import TestCaseDSL, TestRunCreate
from app.services.ability_resolver import annotate_dsl_with_abilities
from app.services.dsl_post_processor import normalize_dsl
from app.services.failure_analyzer import analyze_step_failure, failure_type
from app.utils.url_policy import ensure_allowed_url
from executor.aitp_executor.runner.case_runner import CaseRunner


def create_and_execute_run(db: Session, payload: TestRunCreate) -> TestRun:
    project = db.get(TestProject, payload.project_id)
    if project is None:
        raise ValueError("Project not found.")

    case = db.get(TestCase, payload.case_id) if payload.case_id is not None else None
    if payload.case_id is not None and case is None:
        raise ValueError("Test case not found.")

    system = _resolve_system(db, payload, project)
    dsl = _resolve_dsl(payload, case, project, system)
    dsl = annotate_dsl_with_abilities(
        db,
        dsl,
        instruction=payload.instruction or (case.instruction if case else None),
        project_id=project.id,
        system_id=system.id if system else payload.system_id or project.system_id,
        environment=system.environment if system else project.environment or "test",
    )
    ensure_allowed_url(str(dsl.get("baseUrl") or dsl.get("base_url") or payload.base_url or ""), "base_url")
    run = TestRun(
        run_code=_new_run_code(),
        project_id=project.id,
        system_id=system.id if system else payload.system_id or project.system_id,
        case_id=case.id if case else None,
        instruction=payload.instruction or (case.instruction if case else None),
        base_url=payload.base_url or dsl.get("baseUrl") or (system.base_url if system else project.base_url),
        status="running",
        current_phase="executing",
        dsl_json=_redact_dsl_for_storage(dsl),
        started_at=_utc_now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    _start_background_execution(run.id, dsl)
    return run


def _start_background_execution(run_id: int, dsl: dict) -> None:
    thread = Thread(target=_execute_run_background, args=(run_id, dsl), daemon=True)
    thread.start()


def _execute_run_background(run_id: int, dsl: dict) -> None:
    with SessionLocal() as db:
        run = db.get(TestRun, run_id)
        if run is None:
            return

        run.status = "running"
        run.current_phase = "executing"
        if run.started_at is None:
            run.started_at = _utc_now()
        db.add(run)
        db.commit()

        try:
            execution_result = CaseRunner(event_sink=_runtime_sink(db, run.id)).run(run_code=run.run_code, dsl=dsl)
            _persist_execution_result(db, run, execution_result)
            run.status = "passed" if execution_result["status"] == "passed" else "failed"
            run.current_phase = "completed" if run.status == "passed" else "failed"
            run.summary_json = execution_result["summary"]
        except Exception as exc:
            run.status = "failed"
            run.current_phase = "failed"
            run.summary_json = {"status": "failed", "errorSummary": str(exc)}
        finally:
            run.ended_at = _utc_now()
            db.add(run)
            db.commit()


def list_runs(db: Session) -> list[TestRun]:
    return list(db.scalars(select(TestRun).order_by(TestRun.id.desc())).all())


def get_run(db: Session, run_id: int) -> TestRun | None:
    return db.get(TestRun, run_id)


def list_step_runs(db: Session, run_id: int) -> list[TestStepRun]:
    return list(
        db.scalars(select(TestStepRun).where(TestStepRun.run_id == run_id).order_by(TestStepRun.id)).all()
    )


def list_artifacts(db: Session, run_id: int) -> list[TestArtifact]:
    return list(
        db.scalars(select(TestArtifact).where(TestArtifact.run_id == run_id).order_by(TestArtifact.id)).all()
    )


def latest_screenshot(db: Session, run_id: int) -> TestArtifact | SimpleNamespace | None:
    for artifact_type in ("screenshot", "failure_screenshot", "sandbox_screenshot"):
        artifact = db.scalars(
            select(TestArtifact)
            .where(TestArtifact.run_id == run_id, TestArtifact.artifact_type == artifact_type)
            .order_by(TestArtifact.id.desc())
        ).first()
        if artifact is not None:
            return artifact
    run = db.get(TestRun, run_id)
    if run is None or not run.run_code:
        return None

    from executor.aitp_executor.utils.file_paths import relative_to_project, runs_root, safe_name

    run_root = runs_root() / safe_name(run.run_code)
    candidates = list((run_root / "screenshots").glob("step-*.png"))
    candidates.extend(run_root.glob("sandbox-started.png"))
    if not candidates:
        return None
    latest = max(candidates, key=lambda path: (path.stat().st_mtime, path.name))
    return SimpleNamespace(file_path=relative_to_project(latest))


def report_artifact(db: Session, run_id: int) -> TestArtifact | None:
    artifact = db.scalars(
        select(TestArtifact)
        .where(TestArtifact.run_id == run_id, TestArtifact.artifact_type == "report")
        .order_by(TestArtifact.id.desc())
    ).first()
    if artifact is not None:
        return artifact
    return db.scalars(
        select(TestArtifact)
        .where(TestArtifact.run_id == run_id, TestArtifact.artifact_type == "report_html")
        .order_by(TestArtifact.id.desc())
    ).first()


def list_runtime_messages(db: Session, run_id: int, *, after_id: int = 0) -> list[RuntimeMessage]:
    return list(
        db.scalars(
            select(RuntimeMessage)
            .where(RuntimeMessage.run_id == run_id, RuntimeMessage.id > after_id)
            .order_by(RuntimeMessage.id)
        ).all()
    )


def _resolve_system(db: Session, payload: TestRunCreate, project: TestProject) -> TestSystem | None:
    system_id = payload.system_id or project.system_id
    if system_id is None:
        return None
    system = db.get(TestSystem, system_id)
    if system is None:
        raise ValueError("Test system not found.")
    return system


def _resolve_dsl(
    payload: TestRunCreate,
    case: TestCase | None,
    project: TestProject,
    system: TestSystem | None,
) -> dict:
    if payload.dsl_json is not None:
        dsl = normalize_dsl(payload.dsl_json.model_dump())
    elif case and case.dsl_json:
        dsl = normalize_dsl(TestCaseDSL.model_validate(normalize_dsl(case.dsl_json)).model_dump())
    else:
        raise ValueError("A dsl_json payload or a test case with DSL is required.")

    if payload.base_url:
        dsl["baseUrl"] = payload.base_url
    elif not dsl.get("baseUrl") and system is not None:
        dsl["baseUrl"] = system.login_url or system.base_url
    elif not dsl.get("baseUrl") and project.base_url:
        dsl["baseUrl"] = project.base_url
    return dsl


def _redact_dsl_for_storage(dsl: dict) -> dict:
    redacted = dict(dsl)
    credentials = dict(redacted.get("credentials") or {})
    if "password" in credentials:
        credentials.pop("password")
        credentials["secret_ref"] = credentials.get("secret_ref", "redacted_password")
    redacted["credentials"] = credentials
    redacted["testData"] = dict(redacted.get("testData") or {})

    safe_steps = []
    for step in redacted.get("steps") or []:
        safe_step = dict(step)
        target = str(safe_step.get("target") or "").lower()
        if "password" in target or "密码" in target or "password" in safe_step:
            safe_step["value"] = "***REDACTED***"
            safe_step.pop("password", None)
            if isinstance(safe_step.get("credentials"), dict):
                safe_credentials = dict(safe_step["credentials"])
                if "password" in safe_credentials:
                    safe_credentials.pop("password")
                    safe_credentials["secret_ref"] = safe_credentials.get("secret_ref", "redacted_password")
                safe_step["credentials"] = safe_credentials
        safe_steps.append(safe_step)
    redacted["steps"] = safe_steps
    return redacted


def _persist_execution_result(db: Session, run: TestRun, execution_result: dict) -> None:
    artifacts = execution_result.get("artifacts", {})
    for step_result in execution_result.get("steps", []):
        step_run = TestStepRun(
            run_id=run.id,
            step_id=str(step_result.get("step_id") or step_result.get("step_number")),
            step_name=step_result.get("step_name"),
            action=step_result.get("action"),
            target=step_result.get("target"),
            status=step_result.get("status", "unknown"),
            locator_strategy=step_result.get("locator_strategy"),
            element_ref=step_result.get("element_ref"),
            confidence=step_result.get("confidence"),
            reason=step_result.get("reason"),
            screenshot_path=step_result.get("screenshot_path"),
            error_summary=step_result.get("error_summary"),
            started_at=_parse_dt(step_result.get("started_at")),
            ended_at=_parse_dt(step_result.get("ended_at")),
        )
        db.add(step_run)
        db.flush()
        _add_artifact(
            db,
            run.id,
            step_run.id,
            "screenshot",
            step_result.get("screenshot_path"),
            {"step_number": step_result.get("step_number")},
        )
        _add_artifact(
            db,
            run.id,
            step_run.id,
            "dom_snapshot",
            step_result.get("dom_snapshot_path"),
            {"step_number": step_result.get("step_number")},
        )
        _add_artifact(
            db,
            run.id,
            step_run.id,
            "accessibility_snapshot",
            step_result.get("accessibility_snapshot_path"),
            {"step_number": step_result.get("step_number")},
        )
        if step_run.status == "failed":
            _add_artifact(
                db,
                run.id,
                step_run.id,
                "failure_screenshot",
                step_result.get("screenshot_path"),
                {"step_number": step_result.get("step_number"), "failureType": step_result.get("failure_type")},
            )
            _add_failure_sample(db, run, step_run, step_result, artifacts)

    artifact_types = {
        "summary": "summary",
        "report": "report",
        "step_results": "step_results",
        "locator_debug": "locator_debug",
        "execution_trace": "execution_trace",
        "runtime_stream": "runtime_stream",
        "sandbox_screenshot": "sandbox_screenshot",
    }
    for key, artifact_type in artifact_types.items():
        _add_artifact(db, run.id, None, artifact_type, artifacts.get(key), {"run_code": run.run_code})
    db.commit()


def _add_failure_sample(
    db: Session,
    run: TestRun,
    step_run: TestStepRun,
    step_result: dict,
    artifacts: dict,
) -> None:
    analysis = analyze_step_failure(step_result)
    failure_details = step_result.get("failure_details") if isinstance(step_result.get("failure_details"), dict) else {}
    auth_state = failure_details.get("auth_state") if isinstance(failure_details.get("auth_state"), dict) else {}
    analyzed_failure_type = str(analysis.get("failureType") or failure_type(step_result))
    stored_failure_type = _stored_failure_type(analyzed_failure_type, failure_details, auth_state)
    db.add(
        FailureSample(
            run_id=run.id,
            step_id=step_run.id,
            failure_type=stored_failure_type,
            failure_summary=_failure_sample_summary(stored_failure_type, step_result.get("error_summary")),
            screenshot_path=step_result.get("screenshot_path"),
            dom_snapshot_path=step_result.get("dom_snapshot_path"),
            accessibility_snapshot_path=step_result.get("accessibility_snapshot_path"),
            locator_debug_path=artifacts.get("locator_debug"),
            runtime_stream_path=artifacts.get("runtime_stream"),
            execution_trace_path=artifacts.get("execution_trace"),
            report_path=artifacts.get("report"),
            ai_analysis_json={
                "status": "analyzed",
                "stepAction": step_result.get("action"),
                "target": step_result.get("target"),
                "reason": step_result.get("reason"),
                "failureType": stored_failure_type,
                "guardFailureType": analyzed_failure_type if analyzed_failure_type != stored_failure_type else None,
                "rootCause": failure_details.get("rootCause") or auth_state.get("failureType"),
                "authState": auth_state.get("authState"),
                "remainingRetries": failure_details.get("remainingRetries") or auth_state.get("remainingRetries"),
                "evidence": failure_details.get("evidence") or auth_state.get("evidence"),
                "blockedStep": failure_details.get("blockedStep"),
                "blockedAction": failure_details.get("blockedAction"),
                "requiresHumanAction": failure_details.get("requiresHumanAction") or auth_state.get("requiresHumanAction"),
                "autoRetryDisabled": failure_details.get("autoRetryDisabled"),
                "category": analysis.get("category"),
                "summary": analysis.get("summary"),
                "attemptedStrategies": analysis.get("attemptedStrategies"),
                "suggestedRecovery": analysis.get("suggestedRecovery"),
                "canIntervene": analysis.get("canIntervene"),
                "canGenerateRuleDraft": analysis.get("canGenerateRuleDraft"),
                "visionFallback": analysis.get("visionFallback"),
                "details": step_result.get("failure_details"),
            },
            suggested_rule_json={
                "source": "failure_sample",
                "candidateRuleType": _candidate_rule_type(stored_failure_type),
                "failureType": stored_failure_type,
                "suggestedRecovery": analysis.get("suggestedRecovery"),
                "needsHumanReview": True,
            },
            status="new",
        )
    )


def _stored_failure_type(analysis_failure_type: str, failure_details: dict, auth_state: dict) -> str:
    auth_state_value = str(auth_state.get("authState") or "")
    root_cause = str(failure_details.get("rootCause") or auth_state.get("failureType") or "")
    if (
        auth_state_value in {"login_failed", "login_page"}
        or root_cause in {"login_failed", "auth_state_not_logged_in"}
        or analysis_failure_type in {"protected_step_blocked_by_login_failure", "auth_state_not_logged_in"}
    ):
        return "login_failed" if auth_state_value == "login_failed" or root_cause == "login_failed" else "auth_state_not_logged_in"
    return analysis_failure_type


def _failure_sample_summary(failure_type_value: str, fallback: object) -> str:
    if failure_type_value == "login_failed":
        return "登录未成功，当前未进入业务系统，已停止后续步骤。"
    return str(fallback or "Step failed without error summary.")


def _candidate_rule_type(failure_type_value: object) -> str:
    failure_type_text = str(failure_type_value or "")
    if failure_type_text in {
        "login_failed",
        "protected_step_blocked_by_login_failure",
        "auth_state_not_logged_in",
    }:
        return "login"
    return "recovery_policy"


def _add_artifact(
    db: Session,
    run_id: int,
    step_id: int | None,
    artifact_type: str,
    file_path: str | None,
    metadata: dict,
) -> None:
    if not file_path:
        return
    db.add(
        TestArtifact(
            run_id=run_id,
            step_id=step_id,
            artifact_type=artifact_type,
            file_path=file_path,
            metadata_json=metadata,
        )
    )


def _runtime_sink(db: Session, run_id: int):
    def sink(event: dict) -> None:
        message = RuntimeMessage(
            run_id=run_id,
            type=str(event.get("type") or "text"),
            phase=event.get("phase"),
            content=event.get("content"),
            method=event.get("method"),
            metadata_json=event.get("metadata") or {},
        )
        db.add(message)
        db.commit()

    return sink


def _new_run_code() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"RUN-{stamp}-{uuid4().hex[:8].upper()}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
