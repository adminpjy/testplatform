from datetime import datetime, timezone
from threading import Thread
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    FailureSample,
    RuntimeMessage,
    TestAccount,
    TestArtifact,
    TestCase,
    TestCaseVersion,
    TestProject,
    TestRun,
    TestStepRun,
    TestSystem,
)
from app.schemas.cases import CaseRunCreate, SaveRunAsCaseRequest
from app.schemas.test_runs import TestCaseDSL, TestRunCreate
from app.services.ability_resolver import annotate_dsl_with_abilities
from app.services.dsl_post_processor import normalize_dsl
from app.services.failure_analyzer import analyze_step_failure, failure_type
from app.utils.url_policy import ensure_allowed_url
from app.utils.secrets import decrypt_secret
from executor.aitp_executor.runner.case_runner import CaseRunner


def create_and_execute_run(db: Session, payload: TestRunCreate) -> TestRun:
    project = db.get(TestProject, payload.project_id)
    if project is None:
        raise ValueError("Project not found.")

    case = db.get(TestCase, payload.case_id) if payload.case_id is not None else None
    if payload.case_id is not None and case is None:
        raise ValueError("Test case not found.")

    version = _resolve_version(db, case, payload.case_version_id)
    account = _resolve_account(db, project, case, payload.account_id)
    system = _resolve_system(db, payload, project)
    dsl = _resolve_dsl(payload, case, version, project, system)
    test_data = _merge_dicts(
        case.test_data_json if case else None,
        version.test_data_json if version else None,
        dsl.get("testData"),
        payload.testDataOverride,
    )
    settings = _merge_dicts(
        case.settings_json if case else None,
        version.settings_json if version else None,
        dsl.get("settings"),
        payload.settingsOverride,
    )
    return _create_run_record_and_start(
        db,
        project=project,
        system=system,
        case=case,
        version=version,
        account=account,
        dsl=dsl,
        test_data=test_data,
        settings=settings,
        instruction=payload.instruction or (version.natural_language_goal if version else None) or (case.instruction if case else None),
        base_url=payload.base_url,
        run_name=None,
    )


def create_and_execute_case_run(db: Session, case_id: int, payload: CaseRunCreate) -> TestRun:
    case = db.get(TestCase, case_id)
    if case is None or case.deleted_at is not None or case.status == "deleted":
        raise ValueError("Test case not found.")
    if case.status == "disabled":
        raise ValueError("Disabled test cases cannot be executed.")
    project = db.get(TestProject, case.project_id)
    if project is None:
        raise ValueError("Project not found.")
    version = _resolve_version(db, case, payload.caseVersionId)
    account = _resolve_account(db, project, case, payload.accountId)
    system = db.get(TestSystem, project.system_id) if project.system_id else None
    dsl = _resolve_dsl(TestRunCreate(project_id=project.id), case, version, project, system)
    test_data = _merge_dicts(case.test_data_json, version.test_data_json if version else None, dsl.get("testData"), payload.testDataOverride)
    settings = _merge_dicts(case.settings_json, version.settings_json if version else None, dsl.get("settings"), payload.settingsOverride)
    return _create_run_record_and_start(
        db,
        project=project,
        system=system,
        case=case,
        version=version,
        account=account,
        dsl=dsl,
        test_data=test_data,
        settings=settings,
        instruction=version.natural_language_goal if version else case.instruction,
        base_url=None,
        run_name=payload.runName,
    )


def rerun_test_run(db: Session, run_id: int) -> TestRun:
    source = db.get(TestRun, run_id)
    if source is None:
        raise ValueError("Test run not found.")
    project = db.get(TestProject, source.project_id)
    if project is None:
        raise ValueError("Project not found.")
    case = db.get(TestCase, source.case_id) if source.case_id else None
    version = db.get(TestCaseVersion, source.case_version_id) if source.case_version_id else None
    account = db.get(TestAccount, source.account_id) if source.account_id else None
    system = db.get(TestSystem, source.system_id) if source.system_id else None
    dsl = normalize_dsl(source.dsl_snapshot or source.dsl_json or {})
    return _create_run_record_and_start(
        db,
        project=project,
        system=system,
        case=case,
        version=version,
        account=account,
        dsl=dsl,
        test_data=source.test_data_snapshot or {},
        settings=source.settings_snapshot or {},
        instruction=source.instruction_snapshot or source.instruction,
        base_url=source.base_url_snapshot or source.base_url,
        run_name=f"rerun:{source.run_code}",
    )


def rerun_case_latest(db: Session, case_id: int, payload: CaseRunCreate | None = None) -> TestRun:
    return create_and_execute_case_run(db, case_id, payload or CaseRunCreate())


def run_case_version(db: Session, case_id: int, version_id: int, payload: CaseRunCreate | None = None) -> TestRun:
    payload = payload or CaseRunCreate()
    payload.caseVersionId = version_id
    return create_and_execute_case_run(db, case_id, payload)


def save_run_as_case(db: Session, payload: SaveRunAsCaseRequest) -> TestCase:
    run = db.get(TestRun, payload.runId)
    if run is None:
        raise ValueError("Test run not found.")
    project = db.get(TestProject, payload.projectId)
    if project is None:
        raise ValueError("Project not found.")
    case = TestCase(
        project_id=project.id,
        case_code=f"CASE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}",
        case_name=payload.caseName,
        description=payload.description,
        source_type="manual" if run.status != "failed" else "failure_replay",
        source_run_id=run.id,
        instruction=run.instruction_snapshot or run.instruction,
        natural_language_goal=run.instruction_snapshot or run.instruction,
        inherit_project_account=True,
        account_id=run.account_id,
        test_data_json=run.test_data_snapshot or {},
        settings_json=run.settings_snapshot or {},
        dsl_json=run.dsl_snapshot or run.dsl_json or {},
        status="draft",
    )
    db.add(case)
    db.flush()
    version = TestCaseVersion(
        case_id=case.id,
        version_no=1,
        natural_language_goal=case.natural_language_goal,
        dsl_json=case.dsl_json,
        test_data_json=case.test_data_json,
        settings_json=case.settings_json,
        change_type="saved_from_run",
        change_summary=f"Saved from run {run.run_code}",
        source_run_id=run.id,
    )
    db.add(version)
    db.flush()
    case.current_version_id = version.id
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


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
            if run.started_at and run.ended_at:
                run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
            if run.status == "failed":
                run.error_summary = _run_error_summary(run.summary_json)
            db.add(run)
            db.commit()
            _update_case_run_stats(db, run)


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
    version: TestCaseVersion | None,
    project: TestProject,
    system: TestSystem | None,
) -> dict:
    if payload.dsl_json is not None:
        dsl = normalize_dsl(payload.dsl_json.model_dump())
    elif version and version.dsl_json:
        dsl = normalize_dsl(TestCaseDSL.model_validate(normalize_dsl(version.dsl_json)).model_dump())
    elif case and case.dsl_json:
        dsl = normalize_dsl(TestCaseDSL.model_validate(normalize_dsl(case.dsl_json)).model_dump())
    else:
        raise ValueError("A dsl_json payload or a test case with DSL is required.")

    if payload.base_url:
        dsl["baseUrl"] = payload.base_url
    elif not dsl.get("baseUrl") and system is not None:
        dsl["baseUrl"] = system.login_url or system.base_url
    elif not dsl.get("baseUrl") and project.base_url:
        dsl["baseUrl"] = project.login_url or project.base_url
    return dsl


def _resolve_version(db: Session, case: TestCase | None, version_id: int | None) -> TestCaseVersion | None:
    if case is None:
        return None
    if version_id is not None:
        version = db.get(TestCaseVersion, version_id)
        if version is None or version.case_id != case.id:
            raise ValueError("Test case version not found.")
        return version
    if case.current_version_id:
        version = db.get(TestCaseVersion, case.current_version_id)
        if version is not None:
            return version
    return db.scalars(
        select(TestCaseVersion).where(TestCaseVersion.case_id == case.id).order_by(TestCaseVersion.version_no.desc())
    ).first()


def _resolve_account(db: Session, project: TestProject, case: TestCase | None, account_id: int | None) -> TestAccount | None:
    resolved_id = account_id or (case.account_id if case and case.account_id else None) or project.default_account_id
    if resolved_id is None:
        return None
    account = db.get(TestAccount, resolved_id)
    if account is None or account.deleted_at is not None or account.status == "deleted":
        raise ValueError("Test account not found.")
    return account


def _create_run_record_and_start(
    db: Session,
    *,
    project: TestProject,
    system: TestSystem | None,
    case: TestCase | None,
    version: TestCaseVersion | None,
    account: TestAccount | None,
    dsl: dict,
    test_data: dict,
    settings: dict,
    instruction: str | None,
    base_url: str | None,
    run_name: str | None,
) -> TestRun:
    execution_dsl = normalize_dsl(dict(dsl))
    execution_dsl["testData"] = test_data
    execution_dsl["settings"] = settings
    selected_base_url = base_url or execution_dsl.get("baseUrl") or (system.login_url if system else None) or project.login_url or project.base_url
    if selected_base_url:
        execution_dsl["baseUrl"] = selected_base_url
        ensure_allowed_url(str(selected_base_url), "base_url")
    if account is not None:
        password = decrypt_secret(account.password_encrypted)
        credentials = dict(execution_dsl.get("credentials") or {})
        credentials["username"] = account.username
        if password:
            credentials["password"] = password
            credentials["secret_ref"] = "project_account"
        elif account.secret_ref:
            credentials["secret_ref"] = account.secret_ref
        execution_dsl["credentials"] = credentials
        _hydrate_login_steps(execution_dsl, account, password)
    execution_dsl = annotate_dsl_with_abilities(
        db,
        execution_dsl,
        instruction=instruction,
        project_id=project.id,
        system_id=system.id if system else project.system_id,
        environment=system.environment if system else project.environment or "test",
    )
    redacted_dsl = _redact_dsl_for_storage(execution_dsl)
    run = TestRun(
        run_code=_new_run_code(),
        project_id=project.id,
        system_id=system.id if system else project.system_id,
        case_id=case.id if case else None,
        case_version_id=version.id if version else None,
        account_id=account.id if account else None,
        instruction=instruction,
        instruction_snapshot=instruction,
        base_url=selected_base_url,
        base_url_snapshot=selected_base_url,
        login_url_snapshot=(system.login_url if system else None) or project.login_url,
        home_url_snapshot=(system.home_url if system else None) or project.home_url,
        status="running",
        current_phase="executing",
        dsl_json=redacted_dsl,
        dsl_snapshot=redacted_dsl,
        test_data_snapshot=test_data,
        settings_snapshot=settings,
        account_snapshot=_account_snapshot(account),
        summary_json={"runName": run_name} if run_name else None,
        started_at=_utc_now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    _start_background_execution(run.id, execution_dsl)
    return run


def _merge_dicts(*values: dict | None) -> dict:
    merged: dict = {}
    for value in values:
        if isinstance(value, dict):
            merged.update(value)
    return merged


def _account_snapshot(account: TestAccount | None) -> dict | None:
    if account is None:
        return None
    return {
        "id": account.id,
        "username": account.username,
        "account_name": account.account_name,
        "role_name": account.role_name,
        "allow_read": account.allow_read,
        "allow_write": account.allow_write,
        "allow_approval": account.allow_approval,
        "allow_delete": account.allow_delete,
        "has_password": bool(account.password_encrypted),
        "secret_ref": account.secret_ref,
    }


def _hydrate_login_steps(dsl: dict, account: TestAccount, password: str | None) -> None:
    for step in dsl.get("steps") or []:
        if not isinstance(step, dict):
            continue
        target = str(step.get("target") or "")
        if step.get("action") == "business_goal" and ("登录" in target or "login" in target.lower()):
            step["username"] = account.username
            step.setdefault("credentials", {})
            if isinstance(step["credentials"], dict):
                step["credentials"]["username"] = account.username
                if password:
                    step["credentials"]["password"] = password
                    step["password"] = password
        elif "用户名" in target or "username" in target.lower():
            step["value"] = account.username
        elif password and ("密码" in target or "password" in target.lower()):
            step["value"] = password


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
        "playwright_trace": "playwright_trace",
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
            project_id=run.project_id,
            case_id=run.case_id,
            case_version_id=run.case_version_id,
            run_id=run.id,
            step_id=step_run.id,
            failure_type=stored_failure_type,
            failure_summary=_failure_sample_summary(stored_failure_type, step_result.get("error_summary")),
            evidence_json={
                "runCode": run.run_code,
                "caseId": run.case_id,
                "caseVersionId": run.case_version_id,
                "account": run.account_snapshot,
            },
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


def _run_error_summary(summary_json: dict | None) -> str | None:
    if not isinstance(summary_json, dict):
        return None
    return (
        summary_json.get("errorSummary")
        or summary_json.get("error")
        or (summary_json.get("failedStep") if isinstance(summary_json.get("failedStep"), str) else None)
    )


def _update_case_run_stats(db: Session, run: TestRun) -> None:
    if run.case_id is None:
        return
    case = db.get(TestCase, run.case_id)
    if case is None:
        return
    case.last_run_id = run.id
    case.last_run_status = run.status
    case.last_run_at = run.ended_at or run.created_at
    case.run_count = int(case.run_count or 0) + 1
    if run.status == "passed":
        case.pass_count = int(case.pass_count or 0) + 1
    elif run.status == "failed":
        case.fail_count = int(case.fail_count or 0) + 1
    db.add(case)
    db.commit()


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
    enriched_metadata = dict(metadata or {})
    try:
        from executor.aitp_executor.utils.file_paths import resolve_project_path

        resolved_path = resolve_project_path(file_path)
        if resolved_path.exists() and resolved_path.is_file():
            enriched_metadata.setdefault("file_size_bytes", resolved_path.stat().st_size)
    except Exception:
        pass
    db.add(
        TestArtifact(
            run_id=run_id,
            step_id=step_id,
            artifact_type=artifact_type,
            file_path=file_path,
            metadata_json=enriched_metadata,
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
