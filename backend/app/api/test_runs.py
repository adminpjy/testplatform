import json
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.models import TestCase, TestProject
from app.core.config import settings
from app.schemas.cases import FunctionalTestCaseRead, SaveRunAsCaseRequest
from app.schemas.test_runs import (
    ALLOWED_DSL_ACTIONS,
    AnalyzeResult,
    FailureSampleRead,
    HumanInterventionCreate,
    HumanInterventionRead,
    NaturalLanguageTestRequest,
    RuleDraftRead,
    RuntimeMessageRead,
    TestArtifactRead,
    TestCaseDSL,
    TestRunCreate,
    TestRunRead,
    TestStepRunRead,
    TraceViewerResponse,
)
from app.services.human_interventions import (
    convert_intervention_to_rule_draft,
    create_human_intervention,
    execute_human_intervention,
    list_failure_samples,
    list_human_interventions,
)
from app.services.dsl_post_processor import parse_menu_path
from app.services.ability_resolver import annotate_dsl_with_abilities
from app.services.llm_call_logs import log_llm_call
from app.services.llm_settings import llm_settings_metadata
from app.services.natural_language_parser import NaturalLanguageParser
from app.services.test_run_execution import (
    create_and_execute_run,
    get_run,
    latest_screenshot,
    list_artifacts,
    list_runs,
    list_runtime_messages,
    list_step_runs,
    rerun_test_run,
    save_run_as_case,
)
from app.services.trace_viewer_service import start_trace_viewer, stop_trace_viewer, trace_viewer_status

router = APIRouter()
STREAM_TYPES = {"text", "progress", "warning", "error", "success"}


@router.post("", response_model=TestRunRead, status_code=status.HTTP_201_CREATED)
def create_test_run(payload: TestRunCreate, db: Session = Depends(get_db)) -> TestRunRead:
    try:
        return create_and_execute_run(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[TestRunRead])
def read_test_runs(db: Session = Depends(get_db)) -> list[TestRunRead]:
    return list_runs(db)


@router.post("/analyze", response_model=AnalyzeResult)
def analyze_test_goal(payload: NaturalLanguageTestRequest) -> AnalyzeResult:
    return NaturalLanguageParser().analyze(payload)


@router.post("/analyze-stream")
def stream_analyze_test_goal(payload: NaturalLanguageTestRequest):
    return StreamingResponse(
        _analysis_events(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/plan", response_model=TestCaseDSL)
def plan_test_case(payload: NaturalLanguageTestRequest, db: Session = Depends(get_db)) -> TestCaseDSL:
    parser = NaturalLanguageParser()
    analysis = parser.analyze(payload)
    if not analysis.readyToExecute:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=analysis.model_dump(),
        )

    dsl = parser.plan(payload)
    dsl_data = annotate_dsl_with_abilities(
        db,
        dsl.model_dump(),
        instruction=payload.instruction,
        project_id=payload.project_id,
        system_id=payload.system_id,
    )
    dsl = TestCaseDSL.model_validate(dsl_data)
    if payload.project_id is not None:
        if db.get(TestProject, payload.project_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        test_case = TestCase(
            project_id=payload.project_id,
            case_name=dsl.caseName,
            source_type="natural_language",
            instruction=payload.instruction,
            dsl_json=dsl.model_dump(),
            status="draft",
        )
        db.add(test_case)
        db.commit()
    return dsl


@router.post("/save-as-case", response_model=FunctionalTestCaseRead, status_code=status.HTTP_201_CREATED)
def save_temporary_run_as_case(payload: SaveRunAsCaseRequest, db: Session = Depends(get_db)) -> FunctionalTestCaseRead:
    try:
        return save_run_as_case(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{run_id}/rerun", response_model=TestRunRead, status_code=status.HTTP_201_CREATED)
def rerun_existing_test_run(run_id: int, db: Session = Depends(get_db)) -> TestRunRead:
    try:
        return rerun_test_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{run_id}/steps/{step_id}/intervene", response_model=HumanInterventionRead)
def intervene_test_step(
    run_id: int,
    step_id: int,
    payload: HumanInterventionCreate,
    db: Session = Depends(get_db),
) -> HumanInterventionRead:
    try:
        return create_human_intervention(db, run_id=run_id, step_id=step_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{run_id}/interventions/{intervention_id}/execute", response_model=HumanInterventionRead)
def execute_test_run_intervention(
    run_id: int,
    intervention_id: int,
    db: Session = Depends(get_db),
) -> HumanInterventionRead:
    try:
        return execute_human_intervention(db, run_id=run_id, intervention_id=intervention_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{run_id}/interventions/{intervention_id}/convert-to-rule", response_model=RuleDraftRead)
def convert_test_run_intervention_to_rule(
    run_id: int,
    intervention_id: int,
    db: Session = Depends(get_db),
) -> RuleDraftRead:
    try:
        return convert_intervention_to_rule_draft(db, run_id=run_id, intervention_id=intervention_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{run_id}/stream")
def stream_test_run_runtime(
    run_id: int,
    after_id: int = 0,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: Session = Depends(get_db),
):
    _ensure_run_exists(db, run_id)
    start_after_id = _resolve_start_after_id(after_id, last_event_id)
    return StreamingResponse(
        _runtime_message_events(run_id, start_after_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{run_id}", response_model=TestRunRead)
def read_test_run(run_id: int, db: Session = Depends(get_db)) -> TestRunRead:
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found.")
    return run


@router.get("/{run_id}/steps", response_model=list[TestStepRunRead])
def read_test_run_steps(run_id: int, db: Session = Depends(get_db)) -> list[TestStepRunRead]:
    _ensure_run_exists(db, run_id)
    return list_step_runs(db, run_id)


@router.get("/{run_id}/artifacts", response_model=list[TestArtifactRead])
def read_test_run_artifacts(run_id: int, db: Session = Depends(get_db)) -> list[TestArtifactRead]:
    _ensure_run_exists(db, run_id)
    return list_artifacts(db, run_id)


@router.get("/{run_id}/failure-samples", response_model=list[FailureSampleRead])
def read_test_run_failure_samples(run_id: int, db: Session = Depends(get_db)) -> list[FailureSampleRead]:
    _ensure_run_exists(db, run_id)
    return list_failure_samples(db, run_id=run_id)


@router.get("/{run_id}/interventions", response_model=list[HumanInterventionRead])
def read_test_run_interventions(run_id: int, db: Session = Depends(get_db)) -> list[HumanInterventionRead]:
    _ensure_run_exists(db, run_id)
    return list_human_interventions(db, run_id=run_id)


@router.get("/{run_id}/runtime-messages", response_model=list[RuntimeMessageRead])
def read_runtime_messages(run_id: int, db: Session = Depends(get_db)) -> list[RuntimeMessageRead]:
    _ensure_run_exists(db, run_id)
    return list_runtime_messages(db, run_id)


@router.get("/{run_id}/logs", response_model=list[RuntimeMessageRead])
def read_test_run_logs(run_id: int, db: Session = Depends(get_db)) -> list[RuntimeMessageRead]:
    _ensure_run_exists(db, run_id)
    return list_runtime_messages(db, run_id)


@router.post("/{run_id}/stop", response_model=TestRunRead)
def stop_test_run(run_id: int, db: Session = Depends(get_db)) -> TestRunRead:
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found.")
    if run.status not in {"passed", "failed", "stopped"}:
        run.status = "stopped"
        run.current_phase = "stopped"
        db.add(run)
        db.commit()
        db.refresh(run)
    return run


@router.post("/{run_id}/trace-viewer/start", response_model=TraceViewerResponse)
def start_test_run_trace_viewer(run_id: int, db: Session = Depends(get_db)) -> TraceViewerResponse:
    _ensure_run_exists(db, run_id)
    try:
        return TraceViewerResponse.model_validate(start_trace_viewer(db, run_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{run_id}/trace-viewer/status", response_model=TraceViewerResponse)
def read_test_run_trace_viewer_status(run_id: int, db: Session = Depends(get_db)) -> TraceViewerResponse:
    _ensure_run_exists(db, run_id)
    return TraceViewerResponse.model_validate(trace_viewer_status(run_id))


@router.post("/{run_id}/trace-viewer/stop", response_model=TraceViewerResponse)
def stop_test_run_trace_viewer(run_id: int, db: Session = Depends(get_db)) -> TraceViewerResponse:
    _ensure_run_exists(db, run_id)
    return TraceViewerResponse.model_validate(stop_trace_viewer(run_id))


@router.get("/{run_id}/latest-screenshot")
def read_latest_screenshot(run_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    from executor.aitp_executor.utils.file_paths import resolve_project_path

    _ensure_run_exists(db, run_id)
    artifact = latest_screenshot(db, run_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Latest screenshot not found.")
    path = resolve_project_path(artifact.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenshot file not found.")
    return FileResponse(path, media_type="image/png")


def _ensure_run_exists(db: Session, run_id: int) -> None:
    if get_run(db, run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found.")


def _runtime_message_events(run_id: int, after_id: int) -> Iterator[str]:
    last_id = after_id
    idle_ticks = 0
    while True:
        with SessionLocal() as db:
            messages = list_runtime_messages(db, run_id, after_id=last_id)
            run = get_run(db, run_id)
            run_status = run.status if run is not None else "missing"

        for message in messages:
            last_id = message.id
            yield _format_sse(message)

        if _is_terminal_status(run_status) and not messages:
            break

        if messages:
            idle_ticks = 0
            continue

        idle_ticks += 1
        if idle_ticks % 20 == 0:
            yield ": keep-alive\n\n"
        time.sleep(0.5)


def _format_sse(message) -> str:
    event_type = message.type if message.type in STREAM_TYPES else "text"
    payload = {
        "id": message.id,
        "runId": message.run_id,
        "type": event_type,
        "phase": message.phase,
        "content": message.content,
        "method": message.method,
        "metadata": message.metadata_json or {},
        "createdAt": message.created_at.isoformat() if message.created_at else None,
    }
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"id: {message.id}\nevent: {event_type}\ndata: {data}\n\n"


def _analysis_events(payload: NaturalLanguageTestRequest) -> Iterator[str]:
    event_id = 0
    llm_meta = llm_settings_metadata()

    def emit(message_type: str, phase: str, content: str, method: str, metadata: dict | None = None) -> str:
        nonlocal event_id
        event_id += 1
        body = {
            "id": event_id,
            "runId": None,
            "type": message_type,
            "phase": phase,
            "content": content,
            "method": method,
            "metadata": metadata or {},
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        return f"id: {event_id}\nevent: {message_type}\ndata: {json.dumps(body, ensure_ascii=False, default=str)}\n\n"

    parser = NaturalLanguageParser()
    yield emit(
        "progress",
        "understanding",
        "正在理解测试目标，并准备安全的 LLM 输入。",
        "natural_language_parser",
        {
            "provider": llm_meta.get("provider"),
            "model": llm_meta.get("model"),
            "profileId": llm_meta.get("profileId"),
            "profileName": llm_meta.get("profileName"),
            "endpoint": _safe_llm_endpoint(llm_meta),
            "stream": payload.stream if payload.stream is not None else llm_meta.get("stream"),
            "password_policy": "credentials and password-like text are redacted before prompt construction",
        },
    )
    try:
        sanitized_payload = parser.sanitized_input_payload(payload)
        for path in _menu_paths_from_payload(payload):
            yield emit(
                "progress",
                "dsl_post_process",
                f"检测到测试目标中包含菜单路径：{' / '.join(path)}。",
                "dsl_post_processor",
                {"pathSegments": path, "prompt_key": "dsl_post_process"},
            )
        analyze_request = parser.build_analyze_request(payload)
        yield emit(
            "progress",
            "llm_request",
            f"正在调用 {llm_meta.get('model') or settings.test_llm_model} 分析测试目标。",
            "llm_provider",
            {
                "stage": "analyze",
                "provider": llm_meta.get("provider"),
                "model": llm_meta.get("model"),
                "profileId": llm_meta.get("profileId"),
                "profileName": llm_meta.get("profileName"),
                "endpoint": _safe_llm_endpoint(llm_meta),
                "stream": payload.stream if payload.stream is not None else llm_meta.get("stream"),
                "prompt_key": analyze_request.prompt_key,
                "prompt_version": analyze_request.prompt_version,
                "systemPrompt": analyze_request.system_prompt,
                "userPrompt": analyze_request.user_prompt,
                "inputPayload": sanitized_payload,
            },
        )

        analyze_raw = ""
        chunk_index = 0
        analyze_started = time.monotonic()
        for chunk in parser.provider.stream_complete(analyze_request):
            analyze_raw += chunk
            chunk_index += 1
            yield emit(
                "progress",
                "llm_chunk",
                chunk,
                "llm_provider",
                {"stage": "analyze", "chunkIndex": chunk_index},
            )
        log_llm_call(
            prompt_key=analyze_request.prompt_key,
            prompt_version=analyze_request.prompt_version,
            success=True,
            elapsed_ms=_elapsed_ms(analyze_started),
        )
        yield emit(
            "success",
            "llm_response",
            "LLM 分析回复接收完成。",
            "llm_provider",
            {
                "stage": "analyze",
                "provider": llm_meta.get("provider"),
                "model": llm_meta.get("model"),
                "profileId": llm_meta.get("profileId"),
                "profileName": llm_meta.get("profileName"),
                "prompt_key": analyze_request.prompt_key,
                "prompt_version": analyze_request.prompt_version,
                "chunkCount": chunk_index,
                "rawLength": len(analyze_raw),
            },
        )
        yield emit(
            "progress",
            "json_repair",
            "LLM 分析输出接收完成，正在提取并校验 JSON。",
            "json_utils",
            {"stage": "analyze", "rawLength": len(analyze_raw)},
        )
        analysis = parser.parse_analysis(analyze_raw, payload)
        yield emit(
            "success" if analysis.readyToExecute else "warning",
            "analysis_result",
            "分析完成：信息足够，可以生成 DSL。" if analysis.readyToExecute else "分析完成：需要补充信息。",
            "natural_language_parser",
            {"analysis": analysis.model_dump()},
        )

        dsl = None
        if analysis.readyToExecute:
            plan_request = parser.build_plan_request(payload)
            yield emit(
                "progress",
                "llm_request",
                f"正在调用 {llm_meta.get('model') or settings.test_llm_model} 生成 DSL 步骤。",
                "llm_provider",
                {
                    "stage": "plan",
                    "provider": llm_meta.get("provider"),
                    "model": llm_meta.get("model"),
                    "profileId": llm_meta.get("profileId"),
                    "profileName": llm_meta.get("profileName"),
                    "endpoint": _safe_llm_endpoint(llm_meta),
                    "stream": payload.stream if payload.stream is not None else llm_meta.get("stream"),
                    "prompt_key": plan_request.prompt_key,
                    "prompt_version": plan_request.prompt_version,
                    "systemPrompt": plan_request.system_prompt,
                    "userPrompt": plan_request.user_prompt,
                    "allowedActions": sorted(ALLOWED_DSL_ACTIONS),
                },
            )
            plan_raw = ""
            chunk_index = 0
            plan_started = time.monotonic()
            for chunk in parser.provider.stream_complete(plan_request):
                plan_raw += chunk
                chunk_index += 1
                yield emit(
                    "progress",
                    "llm_chunk",
                    chunk,
                    "llm_provider",
                    {"stage": "plan", "chunkIndex": chunk_index},
                )
            log_llm_call(
                prompt_key=plan_request.prompt_key,
                prompt_version=plan_request.prompt_version,
                success=True,
                elapsed_ms=_elapsed_ms(plan_started),
            )
            yield emit(
                "success",
                "llm_response",
                "LLM DSL 回复接收完成。",
                "llm_provider",
                {
                    "stage": "plan",
                    "provider": llm_meta.get("provider"),
                    "model": llm_meta.get("model"),
                    "profileId": llm_meta.get("profileId"),
                    "profileName": llm_meta.get("profileName"),
                    "prompt_key": plan_request.prompt_key,
                    "prompt_version": plan_request.prompt_version,
                    "chunkCount": chunk_index,
                    "rawLength": len(plan_raw),
                },
            )
            yield emit(
                "progress",
                "json_repair",
                "LLM DSL 输出接收完成，正在提取、修复并校验步骤 JSON。",
                "json_utils",
                {"stage": "plan", "rawLength": len(plan_raw)},
            )
            dsl = parser.parse_plan(plan_raw, payload)
            for normalized in _navigation_normalizations(dsl.model_dump()):
                yield emit(
                    "success",
                    "dsl_post_process",
                    f"已自动规范化步骤：{normalized['originalAction']} → navigate_path，因为目标包含菜单路径。",
                    "dsl_post_processor",
                    normalized,
                )
            for normalized in _login_success_normalizations(dsl.model_dump()):
                yield emit(
                    "success",
                    "dsl_post_process",
                    f"已自动放宽登录成功标识：{normalized['originalAction']} → wait，避免固定等待“工作台”等首页文字。",
                    "dsl_post_processor",
                    normalized,
                )
            yield emit(
                "success",
                "dsl_generated",
                f"DSL 已生成，共 {len(dsl.steps)} 个步骤。",
                "natural_language_parser",
                {"dsl": dsl.model_dump()},
            )

        yield emit(
            "success",
            "completed",
            "自然语言分析流程完成。",
            "natural_language_parser",
            {"analysis": analysis.model_dump(), "dsl": dsl.model_dump() if dsl else None},
        )
    except Exception as exc:
        request = locals().get("plan_request") or locals().get("analyze_request")
        started = locals().get("plan_started") or locals().get("analyze_started")
        if request is not None and started is not None:
            log_llm_call(
                prompt_key=getattr(request, "prompt_key", None),
                prompt_version=getattr(request, "prompt_version", None),
                success=False,
                elapsed_ms=_elapsed_ms(started),
                error_summary=str(exc),
            )
        yield emit(
            "error",
            "failed",
            str(exc),
            "natural_language_parser",
            {"provider": llm_meta.get("provider"), "model": llm_meta.get("model"), "profileId": llm_meta.get("profileId")},
        )


def _resolve_start_after_id(after_id: int, last_event_id: str | None) -> int:
    values = [max(after_id, 0)]
    if last_event_id:
        try:
            values.append(max(int(last_event_id), 0))
        except ValueError:
            pass
    return max(values)


def _is_terminal_status(status_value: str | None) -> bool:
    return status_value in {"passed", "failed", "cancelled", "aborted", "missing"}


def _safe_llm_endpoint(metadata: dict | None = None) -> str | None:
    endpoint = str((metadata or {}).get("endpoint") or settings.test_llm_base_url or "")
    if not endpoint:
        return None
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _menu_paths_from_payload(payload: NaturalLanguageTestRequest) -> list[list[str]]:
    paths: list[list[str]] = []
    for token in re_split_targets(payload.instruction):
        path = parse_menu_path(token)
        if path:
            paths.append(path)
    return paths


def re_split_targets(text: str) -> list[str]:
    import re

    candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9_]+(?:\s*(?:/|>|-|→|\\)\s*[\u4e00-\u9fffA-Za-z0-9_]+)+", text or "")
    return candidates


def _navigation_normalizations(dsl: dict) -> list[dict]:
    results = []
    for step in dsl.get("steps") or []:
        if isinstance(step, dict) and step.get("action") == "navigate_path":
            results.append(
                {
                    "target": step.get("target"),
                    "pathSegments": step.get("pathSegments") or [],
                    "originalAction": step.get("originalAction") or "navigate_path",
                    "normalizedBy": step.get("normalizedBy"),
                    "prompt_key": "dsl_post_process",
                    "prompt_version": "1.0.0",
                }
            )
    return results


def _login_success_normalizations(dsl: dict) -> list[dict]:
    results = []
    for step in dsl.get("steps") or []:
        if (
            isinstance(step, dict)
            and step.get("normalizedBy") == "DslPostProcessor"
            and step.get("normalizationReason")
            == "generic login success text assertion is relaxed to a stabilization wait"
        ):
            results.append(
                {
                    "target": step.get("target"),
                    "originalAction": step.get("originalAction") or "wait_for_text",
                    "originalTarget": step.get("originalTarget"),
                    "normalizedAction": step.get("action"),
                    "prompt_key": "dsl_post_process",
                    "prompt_version": "1.0.0",
                    "reason": "登录后页面可能返回门户首页、业务首页或中间页，不应固定等待通用首页文字。",
                }
            )
    return results
