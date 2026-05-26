import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.models import TestCase, TestProject
from app.schemas.test_runs import (
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
)
from app.services.human_interventions import (
    convert_intervention_to_rule_draft,
    create_human_intervention,
    execute_human_intervention,
    list_failure_samples,
    list_human_interventions,
)
from app.services.natural_language_parser import NaturalLanguageParser
from app.services.test_run_execution import (
    create_and_execute_run,
    get_run,
    latest_screenshot,
    list_artifacts,
    list_runs,
    list_runtime_messages,
    list_step_runs,
)

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
