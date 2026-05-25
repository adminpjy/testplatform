from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import TestCase, TestProject
from app.schemas.test_runs import (
    AnalyzeResult,
    NaturalLanguageTestRequest,
    TestArtifactRead,
    TestCaseDSL,
    TestRunCreate,
    TestRunRead,
    TestStepRunRead,
)
from app.services.natural_language_parser import NaturalLanguageParser
from app.services.test_run_execution import (
    create_and_execute_run,
    get_run,
    latest_screenshot,
    list_artifacts,
    list_runs,
    list_step_runs,
)

router = APIRouter()


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
