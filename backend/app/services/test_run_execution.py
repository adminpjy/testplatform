from datetime import datetime, timezone
import json
import os
import re
from threading import Thread
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.db.session import SessionLocal
from app.models import (
    FailureSample,
    RuntimeMessage,
    TestAccount,
    TestArtifact,
    TestCase,
    TestCaseVersion,
    PlatformUser,
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
from app.services.llm_settings import get_active_llm_config
from app.services.natural_language_parser import NaturalLanguageParser
from app.services.permissions import accessible_project_ids
from app.utils.url_policy import ensure_allowed_url
from app.utils.secrets import decrypt_secret
from executor.aitp_executor.runner.case_runner import CaseRunner


TERMINAL_RUN_STATUSES = {"passed", "failed", "stopped", "cancelled", "aborted"}


def create_and_execute_run(
    db: Session,
    payload: TestRunCreate,
    *,
    actor_user_id: int | None = None,
    campaign_id: int | None = None,
) -> TestRun:
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
    instruction = payload.instruction or (version.natural_language_goal if version else None) or (case.instruction if case else None)
    test_data = _apply_instruction_record_criteria(test_data, instruction)
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
        instruction=instruction,
        base_url=payload.base_url,
        run_name=None,
        actor_user_id=actor_user_id,
        campaign_id=campaign_id,
    )


def create_and_execute_case_run(
    db: Session,
    case_id: int,
    payload: CaseRunCreate,
    *,
    actor_user_id: int | None = None,
    campaign_id: int | None = None,
) -> TestRun:
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
        actor_user_id=actor_user_id,
        campaign_id=campaign_id,
    )


def rerun_test_run(db: Session, run_id: int, *, actor_user_id: int | None = None) -> TestRun:
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
    dsl = _source_dsl_for_rerun(source, account=account)
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
        actor_user_id=actor_user_id,
        campaign_id=source.campaign_id,
    )


def recover_test_run_from_intervention(
    db: Session,
    run_id: int,
    *,
    intervention_id: int,
    step_run_id: int | None,
    plan: dict,
) -> TestRun:
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
    failed_step = db.get(TestStepRun, step_run_id) if step_run_id else None
    dsl = _source_dsl_for_rerun(source, account=account)
    recovery_steps = _intervention_plan_steps_to_dsl(plan, failed_step=failed_step)
    if recovery_steps:
        failed_index = _failed_step_index(db, run_id=run_id, failed_step=failed_step, dsl=dsl)
        dsl = _insert_intervention_steps(dsl, recovery_steps, failed_index)
    settings = dict(source.settings_snapshot or {})
    settings["humanIntervention"] = {
        "sourceRunId": run_id,
        "sourceRunCode": source.run_code,
        "interventionId": intervention_id,
        "failedStepRunId": step_run_id,
        "insertedStepCount": len(recovery_steps),
        "plan": plan,
    }
    return _create_run_record_and_start(
        db,
        project=project,
        system=system,
        case=case,
        version=version,
        account=account,
        dsl=dsl,
        test_data=source.test_data_snapshot or {},
        settings=settings,
        instruction=source.instruction_snapshot or source.instruction,
        base_url=source.base_url_snapshot or source.base_url,
        run_name=f"recovery:{source.run_code}",
    )


def rerun_case_latest(
    db: Session,
    case_id: int,
    payload: CaseRunCreate | None = None,
    *,
    actor_user_id: int | None = None,
) -> TestRun:
    return create_and_execute_case_run(db, case_id, payload or CaseRunCreate(), actor_user_id=actor_user_id)


def run_case_version(
    db: Session,
    case_id: int,
    version_id: int,
    payload: CaseRunCreate | None = None,
    *,
    actor_user_id: int | None = None,
) -> TestRun:
    payload = payload or CaseRunCreate()
    payload.caseVersionId = version_id
    return create_and_execute_case_run(db, case_id, payload, actor_user_id=actor_user_id)


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


def _source_dsl_for_rerun(source: TestRun, *, account: TestAccount | None) -> dict:
    dsl = source.dsl_snapshot or source.dsl_json
    if not isinstance(dsl, dict) or not dsl.get("steps"):
        raise ValueError("运行记录没有保存可执行 DSL 快照，无法直接重跑。请重新分析或选择包含 DSL 的运行记录。")
    if _requires_unavailable_runtime_password(source, dsl, account=account):
        raise ValueError(
            "该运行记录使用的是临时输入的密码，系统只保存脱敏快照，不保存明文密码。"
            "请先为项目配置测试账号，或点击该运行记录带入配置后补充密码再执行。"
        )
    return normalize_dsl(dsl)


def _requires_unavailable_runtime_password(
    source: TestRun,
    dsl: dict,
    *,
    account: TestAccount | None,
) -> bool:
    if account is not None:
        return False
    credentials = dsl.get("credentials") if isinstance(dsl.get("credentials"), dict) else {}
    secret_ref = str(credentials.get("secret_ref") or "")
    if secret_ref not in {"runtime_form_password", "redacted_password"}:
        return False
    if source.account_id is not None:
        return True
    return bool(credentials.get("username") or _dsl_contains_login_step(dsl))


def _dsl_contains_login_step(dsl: dict) -> bool:
    for step in dsl.get("steps") or []:
        if not isinstance(step, dict):
            continue
        text = " ".join(
            str(step.get(key) or "")
            for key in ["action", "target", "intent", "description", "name", "stepName", "step_name"]
        ).lower()
        if "登录" in text or "登陆" in text or "login" in text or "signin" in text:
            return True
    return False


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
            _apply_executor_runtime_env(dsl)
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


def _apply_executor_runtime_env(dsl: dict | None = None) -> None:
    run_settings = dsl.get("settings") if isinstance(dsl, dict) and isinstance(dsl.get("settings"), dict) else {}
    values = {
        "EXECUTOR_MODE": app_settings.executor_mode,
        "CUBE_API_URL": app_settings.cube_api_url,
        "CUBE_BROWSER_TEMPLATE_ID": app_settings.cube_browser_template_id,
        "CUBE_TEMPLATE_ID": app_settings.cube_template_id,
        "CUBE_CDP_PORT": str(app_settings.cube_cdp_port),
        "CUBE_SANDBOX_TIMEOUT_SECONDS": str(app_settings.cube_sandbox_timeout_seconds),
        "CUBE_SANDBOX_TTL_SECONDS": str(app_settings.cube_sandbox_ttl_seconds),
        "KEEP_SANDBOX_ON_FAILURE": _bool_string(app_settings.keep_sandbox_on_failure),
        "LOCAL_BROWSER": _bool_string(app_settings.local_browser),
        "PLAYWRIGHT_IGNORE_HTTPS_ERRORS": _bool_string(app_settings.playwright_ignore_https_errors),
        "PLAYWRIGHT_AUTO_CONTINUE_SECURITY_INTERSTITIAL": _bool_string(
            app_settings.playwright_auto_continue_security_interstitial
        ),
        "PLAYWRIGHT_PROXY_SERVER": app_settings.playwright_proxy_server,
        "PLAYWRIGHT_PROXY_BYPASS": app_settings.playwright_proxy_bypass,
        "PLAYWRIGHT_PROXY_USERNAME": app_settings.playwright_proxy_username,
        "PLAYWRIGHT_USER_AGENT": app_settings.playwright_user_agent,
        "GOAL_MAX_ITERATIONS": str(app_settings.goal_max_iterations),
        "GOAL_TOTAL_TIMEOUT_MS": str(app_settings.goal_total_timeout_ms),
        "GOAL_SINGLE_ACTION_TIMEOUT_MS": str(app_settings.goal_single_action_timeout_ms),
    }
    try:
        llm_config = get_active_llm_config()
        vision_enabled = _vision_enabled_for_run(run_settings, has_active_model=bool(llm_config.base_url and llm_config.api_key))
        values.update(
            {
                "LLM_PROVIDER": llm_config.provider,
                "TEST_LLM_BASE_URL": llm_config.base_url,
                "TEST_LLM_API_KEY": llm_config.api_key,
                "TEST_LLM_MODEL": llm_config.model,
                "TEST_LLM_TIMEOUT_SECONDS": str(llm_config.timeout_seconds),
                "TEST_LLM_MAX_TOKENS": str(llm_config.max_tokens),
                "TEST_LLM_TEMPERATURE": str(llm_config.temperature),
                "TEST_LLM_TOP_P": str(llm_config.top_p),
                "TEST_LLM_VERIFY_SSL": _bool_string(llm_config.verify_ssl),
                "TEST_LLM_CA_BUNDLE": llm_config.ca_bundle,
                "TEST_LLM_TRUST_ENV": _bool_string(llm_config.trust_env),
                "VISION_FALLBACK_ENABLED": _bool_string(vision_enabled),
                "VISION_MODEL_PROVIDER": app_settings.vision_model_provider or llm_config.provider,
                "VISION_MODEL_ENDPOINT": app_settings.vision_model_endpoint or llm_config.base_url,
                "VISION_MODEL_API_KEY": (
                    app_settings.vision_model_api_key.get_secret_value()
                    if app_settings.vision_model_api_key
                    else llm_config.api_key
                ),
                "VISION_MODEL_NAME": app_settings.vision_model_name or llm_config.model,
                "VISION_MODEL_TIMEOUT": str(app_settings.vision_model_timeout or llm_config.timeout_seconds),
                "VISION_MODEL_VERIFY_SSL": _bool_string(app_settings.vision_model_verify_ssl if app_settings.vision_model_endpoint else llm_config.verify_ssl),
                "VISION_MODEL_CA_BUNDLE": app_settings.vision_model_ca_bundle or llm_config.ca_bundle,
                "VISION_MODEL_TRUST_ENV": _bool_string(app_settings.vision_model_trust_env if app_settings.vision_model_endpoint else llm_config.trust_env),
            }
        )
    except Exception:
        fallback_has_model = bool(app_settings.test_llm_base_url and app_settings.test_llm_api_key)
        vision_enabled = _vision_enabled_for_run(run_settings, has_active_model=fallback_has_model)
        values.update(
            {
                "LLM_PROVIDER": app_settings.llm_provider,
                "TEST_LLM_BASE_URL": app_settings.test_llm_base_url,
                "TEST_LLM_MODEL": app_settings.test_llm_model,
                "TEST_LLM_TIMEOUT_SECONDS": str(app_settings.test_llm_timeout_seconds),
                "TEST_LLM_MAX_TOKENS": str(app_settings.test_llm_max_tokens),
                "TEST_LLM_TEMPERATURE": str(app_settings.test_llm_temperature),
                "TEST_LLM_TOP_P": str(app_settings.test_llm_top_p),
                "TEST_LLM_VERIFY_SSL": _bool_string(app_settings.test_llm_verify_ssl),
                "TEST_LLM_CA_BUNDLE": app_settings.test_llm_ca_bundle,
                "TEST_LLM_TRUST_ENV": _bool_string(app_settings.test_llm_trust_env),
                "VISION_FALLBACK_ENABLED": _bool_string(vision_enabled),
                "VISION_MODEL_PROVIDER": app_settings.vision_model_provider or app_settings.llm_provider,
                "VISION_MODEL_ENDPOINT": app_settings.vision_model_endpoint or app_settings.test_llm_base_url,
                "VISION_MODEL_NAME": app_settings.vision_model_name or app_settings.test_llm_model,
                "VISION_MODEL_TIMEOUT": str(app_settings.vision_model_timeout or app_settings.test_llm_timeout_seconds),
                "VISION_MODEL_VERIFY_SSL": _bool_string(app_settings.vision_model_verify_ssl if app_settings.vision_model_endpoint else app_settings.test_llm_verify_ssl),
                "VISION_MODEL_CA_BUNDLE": app_settings.vision_model_ca_bundle or app_settings.test_llm_ca_bundle,
                "VISION_MODEL_TRUST_ENV": _bool_string(app_settings.vision_model_trust_env if app_settings.vision_model_endpoint else app_settings.test_llm_trust_env),
            }
        )
        if app_settings.test_llm_api_key:
            values["TEST_LLM_API_KEY"] = app_settings.test_llm_api_key.get_secret_value()
        if app_settings.vision_model_api_key:
            values["VISION_MODEL_API_KEY"] = app_settings.vision_model_api_key.get_secret_value()
        elif app_settings.test_llm_api_key:
            values["VISION_MODEL_API_KEY"] = app_settings.test_llm_api_key.get_secret_value()
    if app_settings.playwright_proxy_password:
        values["PLAYWRIGHT_PROXY_PASSWORD"] = app_settings.playwright_proxy_password.get_secret_value()
    for key, value in values.items():
        os.environ[key] = str(value or "")


def _bool_string(value: bool) -> str:
    return "true" if value else "false"


def _default_vision_fallback_enabled(project: TestProject) -> bool:
    if bool(getattr(project, "enable_vision_fallback_default", False)):
        return True
    if app_settings.vision_fallback_enabled:
        return True
    try:
        active = get_active_llm_config()
        return bool(active.base_url and active.api_key)
    except Exception:
        return bool(app_settings.test_llm_base_url and app_settings.test_llm_api_key)


def _vision_enabled_for_run(run_settings: dict, *, has_active_model: bool) -> bool:
    if "visionFallbackEnabled" in run_settings:
        return bool(run_settings.get("visionFallbackEnabled"))
    if "vision_fallback_enabled" in run_settings:
        return bool(run_settings.get("vision_fallback_enabled"))
    return bool(app_settings.vision_fallback_enabled or has_active_model)


def list_runs(db: Session, user: PlatformUser | None = None) -> list[TestRun]:
    query = select(TestRun)
    if user is not None:
        project_ids = accessible_project_ids(db, user)
        if project_ids is not None:
            if not project_ids:
                return []
            query = query.where(TestRun.project_id.in_(project_ids))
    runs = list(db.scalars(query.order_by(TestRun.id.desc())).all())
    changed = False
    for run in runs:
        changed = _reconcile_run_lifecycle(db, run, commit=False) or changed
    if changed:
        db.commit()
        for run in runs:
            db.refresh(run)
    return runs


def get_run(db: Session, run_id: int) -> TestRun | None:
    run = db.get(TestRun, run_id)
    if run is not None:
        _reconcile_run_lifecycle(db, run)
    return run


def _reconcile_run_lifecycle(db: Session, run: TestRun, *, commit: bool = True) -> bool:
    if run.status != "running":
        return False

    summary = _load_executor_summary(run.run_code)
    if isinstance(summary, dict) and str(summary.get("status") or "") in TERMINAL_RUN_STATUSES:
        status_value = str(summary.get("status"))
        run.status = status_value
        run.current_phase = "completed" if status_value == "passed" else status_value
        run.summary_json = _merge_summary_json(run.summary_json, summary)
        run.started_at = run.started_at or _parse_dt(summary.get("startedAt"))
        run.ended_at = _parse_dt(summary.get("endedAt")) or run.ended_at or _utc_now()
        run.duration_ms = _coerce_int(summary.get("durationMs")) or run.duration_ms
        if status_value == "failed":
            run.error_summary = _run_error_summary(run.summary_json)
        db.add(run)
        if commit:
            db.commit()
            db.refresh(run)
        return True

    if _running_run_timed_out(run):
        timeout_seconds = _run_timeout_seconds()
        summary_json = _merge_summary_json(
            run.summary_json,
            {
                "status": "failed",
                "errorSummary": f"execution_timeout: 运行超过 {timeout_seconds} 秒仍未结束，系统已自动收尾为失败。",
            },
        )
        run.status = "failed"
        run.current_phase = "failed"
        run.summary_json = summary_json
        run.error_summary = _run_error_summary(summary_json)
        run.ended_at = _utc_now()
        started = _as_aware_utc(run.started_at or run.created_at)
        if started:
            run.duration_ms = int((run.ended_at - started).total_seconds() * 1000)
        db.add(run)
        if commit:
            db.commit()
            db.refresh(run)
        return True

    return False


def _load_executor_summary(run_code: str | None) -> dict | None:
    if not run_code:
        return None
    try:
        from executor.aitp_executor.utils.file_paths import runs_root, safe_name

        path = runs_root() / safe_name(run_code) / "summary.json"
        if not path.exists() or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _merge_summary_json(existing: dict | None, summary: dict) -> dict:
    merged = dict(existing or {})
    merged.update(summary)
    return merged


def _running_run_timed_out(run: TestRun) -> bool:
    started = _as_aware_utc(run.started_at or run.created_at)
    if started is None:
        return False
    return (_utc_now() - started).total_seconds() > _run_timeout_seconds()


def _run_timeout_seconds() -> int:
    candidates = [
        int(app_settings.run_timeout_seconds or 0),
        int(app_settings.cube_sandbox_timeout_seconds or 0),
    ]
    return max([value for value in candidates if value > 0] or [600]) + 60


def list_step_runs(db: Session, run_id: int) -> list[TestStepRun]:
    return list(
        db.scalars(select(TestStepRun).where(TestStepRun.run_id == run_id).order_by(TestStepRun.id)).all()
    )


def list_artifacts(db: Session, run_id: int) -> list[TestArtifact]:
    artifacts = list(
        db.scalars(select(TestArtifact).where(TestArtifact.run_id == run_id).order_by(TestArtifact.id)).all()
    )
    return artifacts + _runtime_process_screenshot_artifacts(db, run_id, artifacts)


def _runtime_process_screenshot_artifacts(
    db: Session,
    run_id: int,
    stored_artifacts: list[TestArtifact],
) -> list[SimpleNamespace]:
    run = db.get(TestRun, run_id)
    if run is None or not run.run_code:
        return []
    stored_paths = {artifact.file_path for artifact in stored_artifacts if artifact.file_path}
    try:
        from executor.aitp_executor.utils.file_paths import runs_root, safe_name

        manifest = runs_root() / safe_name(run.run_code) / "process-screenshots.jsonl"
    except Exception:
        return []
    if not manifest.exists():
        return []

    step_id_by_number = _step_id_by_number(db, run_id)
    records: list[SimpleNamespace] = []
    with manifest.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            file_path = str(record.get("path") or "")
            if not file_path or file_path in stored_paths:
                continue
            step_number = _coerce_int(record.get("step_number"))
            metadata = {
                "step_number": step_number,
                "index": record.get("index") or index,
                "label": record.get("label"),
                "url": record.get("url"),
                "title": record.get("title"),
                "metadata": record.get("metadata") or {},
            }
            records.append(
                SimpleNamespace(
                    id=-index,
                    run_id=run_id,
                    step_id=step_id_by_number.get(step_number),
                    artifact_type="process_screenshot",
                    file_path=file_path,
                    metadata_json=metadata,
                    created_at=_parse_dt(record.get("created_at")) or _utc_now(),
                )
            )
    return records


def _step_id_by_number(db: Session, run_id: int) -> dict[int, int]:
    step_runs = list(
        db.scalars(select(TestStepRun).where(TestStepRun.run_id == run_id).order_by(TestStepRun.id)).all()
    )
    mapping: dict[int, int] = {}
    for index, step in enumerate(step_runs, start=1):
        mapping[index] = step.id
        number = _coerce_int(step.step_id)
        if number is not None:
            mapping[number] = step.id
    return mapping


def latest_screenshot(db: Session, run_id: int) -> TestArtifact | SimpleNamespace | None:
    run = db.get(TestRun, run_id)
    if run is None or not run.run_code:
        return None
    runtime_screenshot = _latest_runtime_screenshot_file(run.run_code)
    if runtime_screenshot is not None:
        return runtime_screenshot
    for artifact_type in ("screenshot", "failure_screenshot", "sandbox_screenshot"):
        artifact = db.scalars(
            select(TestArtifact)
            .where(TestArtifact.run_id == run_id, TestArtifact.artifact_type == artifact_type)
            .order_by(TestArtifact.id.desc())
        ).first()
        if artifact is not None:
            return artifact
    return None


def _latest_runtime_screenshot_file(run_code: str) -> SimpleNamespace | None:
    try:
        from executor.aitp_executor.utils.file_paths import relative_to_project, runs_root, safe_name

        run_root = runs_root() / safe_name(run_code)
        screenshot_root = run_root / "screenshots"
        candidates = [path for path in screenshot_root.glob("step-*.png") if path.is_file()]
        sandbox = screenshot_root / "sandbox-started.png"
        if sandbox.exists() and sandbox.is_file():
            candidates.append(sandbox)
        if not candidates:
            return None
        latest = max(candidates, key=lambda path: (path.stat().st_mtime, path.name))
        return SimpleNamespace(file_path=relative_to_project(latest))
    except Exception:
        return None


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
    actor_user_id: int | None = None,
    campaign_id: int | None = None,
) -> TestRun:
    execution_dsl = normalize_dsl(dict(dsl))
    execution_dsl["testData"] = test_data
    settings = dict(settings or {})
    if "visionFallbackEnabled" not in settings and "vision_fallback_enabled" not in settings:
        settings["visionFallbackEnabled"] = _default_vision_fallback_enabled(project)
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
        campaign_id=campaign_id,
        account_id=account.id if account else None,
        created_by_user_id=actor_user_id,
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


def _intervention_plan_steps_to_dsl(plan: dict, *, failed_step: TestStepRun | None = None) -> list[dict]:
    steps: list[dict] = []
    structured_retry_only = _requires_structured_retry(failed_step)
    for item in plan.get("steps") or []:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "")
        target = str(item.get("target") or "")
        value = item.get("value")
        reason = str(item.get("reason") or "")
        base = {
            "source": "human_intervention",
            "sourceAction": action,
            "reason": reason,
        }
        if structured_retry_only and action not in {"wait", "close_dialog", "assert_text_exists", "assert_url_contains"}:
            continue
        if action == "wait":
            wait_ms = _coerce_wait_ms(value)
            steps.append({**base, "action": "wait", "target": target or "等待页面稳定", "ms": wait_ms})
        elif action == "click":
            if target:
                steps.append({**base, "action": "click", "target": target})
        elif action == "input":
            if target and value not in (None, ""):
                steps.append({**base, "action": "input", "target": target, "value": str(value)})
        elif action == "select":
            if target and value not in (None, ""):
                steps.append({**base, "action": "select", "target": target, "value": str(value)})
        elif action == "choose_radio":
            if target:
                steps.append({**base, "action": "click", "target": target})
        elif action == "close_dialog":
            steps.append({**base, "action": "close_dialog_by_common_controls", "target": target or "当前弹窗"})
        elif action == "confirm_dialog":
            steps.append({**base, "action": "confirm_dialog", "target": target or "确定"})
        elif action == "assert_text_exists":
            if target:
                steps.append({**base, "action": "assert_text_exists", "target": target, "text": target})
        elif action == "assert_url_contains":
            if target:
                steps.append({**base, "action": "assert_url_contains", "target": target, "text": target})
    return steps


def _requires_structured_retry(failed_step: TestStepRun | None) -> bool:
    if failed_step is None:
        return False
    combined = " ".join(
        str(item or "")
        for item in [
            getattr(failed_step, "action", None),
            getattr(failed_step, "target", None),
            getattr(failed_step, "step_name", None),
            getattr(failed_step, "locator_strategy", None),
            getattr(failed_step, "reason", None),
            getattr(failed_step, "error_summary", None),
        ]
    )
    return any(token in combined for token in ["process_table_rows", "for_each_table_row", "table_row_loop_failed"])


def _insert_intervention_steps(dsl: dict, recovery_steps: list[dict], failed_index: int | None) -> dict:
    next_dsl = dict(dsl)
    original_steps = [dict(step) for step in next_dsl.get("steps") or [] if isinstance(step, dict)]
    if not original_steps:
        next_dsl["steps"] = recovery_steps
        return next_dsl
    insert_at = failed_index if failed_index is not None else len(original_steps)
    insert_at = max(0, min(insert_at, len(original_steps)))
    next_dsl["steps"] = original_steps[:insert_at] + recovery_steps + original_steps[insert_at:]
    return next_dsl


def _failed_step_index(db: Session, *, run_id: int, failed_step: TestStepRun | None, dsl: dict) -> int | None:
    if failed_step is not None and failed_step.step_id:
        match = re.search(r"(\d+)", str(failed_step.step_id))
        if match:
            index = int(match.group(1)) - 1
            if index >= 0:
                return index
    if failed_step is not None:
        ordered = list(
            db.scalars(select(TestStepRun).where(TestStepRun.run_id == run_id).order_by(TestStepRun.id)).all()
        )
        for index, item in enumerate(ordered):
            if item.id == failed_step.id:
                return index
    steps = dsl.get("steps") or []
    return len(steps) - 1 if steps else None


def _coerce_wait_ms(value: object) -> int:
    try:
        wait_ms = int(float(str(value or "3000").strip()))
    except (TypeError, ValueError):
        wait_ms = 3000
    return max(100, min(wait_ms, 60000))


def _merge_dicts(*values: dict | None) -> dict:
    merged: dict = {}
    for value in values:
        if isinstance(value, dict):
            merged.update(value)
    return merged


def _apply_instruction_record_criteria(test_data: dict, instruction: str | None) -> dict:
    criteria = NaturalLanguageParser._extract_instruction_record_criteria(instruction)
    if not criteria:
        return test_data
    merged = dict(test_data or {})
    for field, value in criteria.items():
        aliases = _record_field_aliases(field)
        matched = [alias for alias in aliases if alias in merged]
        if matched:
            for alias in matched:
                merged[alias] = value
        else:
            merged[field] = value
    return merged


def _record_field_aliases(field: str) -> list[str]:
    if "实例号" in field:
        return ["实例号", "流程实例号", "instanceNo", "instance_no", "processInstanceId", "process_instance_id"]
    if field in {"编号", "单据编号", "单号", "申请编号", "工单号"}:
        return [field, "编号", "单据编号", "单号", "申请编号", "工单号", "recordNo", "record_no"]
    return [field]


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
        elif step.get("action") in {"fill_form", "auto_fill_form"} and ("登录" in target or "login" in target.lower()):
            step.setdefault("formData", {})
            if isinstance(step["formData"], dict):
                step["formData"]["username"] = account.username
                if password:
                    step["formData"]["password"] = password
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
    redacted["testData"] = _redact_sensitive_mapping(dict(redacted.get("testData") or {}))

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
        if isinstance(safe_step.get("formData"), dict):
            safe_step["formData"] = _redact_sensitive_mapping(dict(safe_step["formData"]))
        if isinstance(safe_step.get("testData"), dict):
            safe_step["testData"] = _redact_sensitive_mapping(dict(safe_step["testData"]))
        safe_steps.append(safe_step)
    redacted["steps"] = safe_steps
    return redacted


def _redact_sensitive_mapping(value: dict) -> dict:
    redacted = {}
    for key, item in value.items():
        if "password" in str(key).lower() or "secret" in str(key).lower() or "密码" in str(key) or "口令" in str(key):
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = item
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
        for process_screenshot in step_result.get("process_screenshots") or []:
            if not isinstance(process_screenshot, dict):
                continue
            _add_artifact(
                db,
                run.id,
                step_run.id,
                "process_screenshot",
                process_screenshot.get("path") or process_screenshot.get("file_path"),
                {
                    "step_number": step_result.get("step_number"),
                    "index": process_screenshot.get("index"),
                    "label": process_screenshot.get("label"),
                    "url": process_screenshot.get("url"),
                    "title": process_screenshot.get("title"),
                    "metadata": process_screenshot.get("metadata") or {},
                },
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
        "process_screenshots": "process_screenshots",
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
        auth_state_value == "login_captcha_required"
        or root_cause == "authentication_challenge_required"
        or analysis_failure_type in {"protected_step_blocked_by_auth_challenge", "login_captcha_required", "authentication_challenge_required"}
    ):
        return "login_captcha_required"
    if analysis_failure_type == "protected_step_blocked_by_login_failure":
        return "protected_step_blocked_by_login_failure"
    if auth_state_value == "login_failed" or root_cause == "login_failed":
        return "login_failed"
    if auth_state_value == "login_page" or root_cause == "auth_state_not_logged_in" or analysis_failure_type == "auth_state_not_logged_in":
        return "auth_state_not_logged_in"
    return analysis_failure_type


def _failure_sample_summary(failure_type_value: str, fallback: object) -> str:
    if failure_type_value == "login_captcha_required":
        return "登录失败后触发验证码或二次认证，当前未进入业务系统，已停止后续步骤。"
    if failure_type_value == "login_failed":
        return "登录未成功，当前未进入业务系统，已停止后续步骤。"
    return str(fallback or "Step failed without error summary.")


def _candidate_rule_type(failure_type_value: object) -> str:
    failure_type_text = str(failure_type_value or "")
    if failure_type_text in {
        "login_failed",
        "login_captcha_required",
        "protected_step_blocked_by_login_failure",
        "protected_step_blocked_by_auth_challenge",
        "authentication_challenge_required",
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


def _coerce_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return _as_aware_utc(value)
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return _as_aware_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _as_aware_utc(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
