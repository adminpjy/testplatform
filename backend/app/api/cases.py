from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cases import (
    CaseAnalyzeRequest,
    DslPayload,
    DslValidationResult,
    FailureAnalysisRead,
    FixApplicationRead,
    FunctionalTestCaseRead,
    FunctionalTestCaseUpdate,
    SaveGeneratedDslRequest,
    TestCaseVersionCreate,
    TestCaseVersionRead,
)
from app.schemas.test_runs import AnalyzeResult, FailureSampleRead, TestRunRead
from app.services.cases import (
    activate_version,
    analyze_case,
    copy_case,
    create_version,
    format_dsl,
    generate_case_dsl,
    get_case,
    get_version,
    list_case_failure_analyses,
    list_case_failure_samples,
    list_case_fix_applications,
    list_case_runs,
    list_versions,
    save_generated_dsl,
    set_case_status,
    soft_delete_case,
    update_case,
    update_case_dsl,
    validate_dsl,
)

router = APIRouter()


@router.get("/{case_id}", response_model=FunctionalTestCaseRead)
def read_case(case_id: int, db: Session = Depends(get_db)) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id)
    return case


@router.put("/{case_id}", response_model=FunctionalTestCaseRead)
def update_functional_case(
    case_id: int,
    payload: FunctionalTestCaseUpdate,
    db: Session = Depends(get_db),
) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id)
    try:
        return update_case(db, case, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_functional_case(case_id: int, db: Session = Depends(get_db)) -> None:
    case = _case_or_404(db, case_id)
    soft_delete_case(db, case)


@router.post("/{case_id}/disable", response_model=FunctionalTestCaseRead)
def disable_case(case_id: int, db: Session = Depends(get_db)) -> FunctionalTestCaseRead:
    return set_case_status(db, _case_or_404(db, case_id), "disabled")


@router.post("/{case_id}/enable", response_model=FunctionalTestCaseRead)
def enable_case(case_id: int, db: Session = Depends(get_db)) -> FunctionalTestCaseRead:
    return set_case_status(db, _case_or_404(db, case_id), "active")


@router.post("/{case_id}/copy", response_model=FunctionalTestCaseRead, status_code=status.HTTP_201_CREATED)
def copy_functional_case(case_id: int, db: Session = Depends(get_db)) -> FunctionalTestCaseRead:
    try:
        return copy_case(db, _case_or_404(db, case_id))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case code already exists.") from exc


@router.get("/{case_id}/versions", response_model=list[TestCaseVersionRead])
def read_case_versions(case_id: int, db: Session = Depends(get_db)) -> list[TestCaseVersionRead]:
    _case_or_404(db, case_id)
    return list_versions(db, case_id)


@router.get("/{case_id}/versions/{version_id}", response_model=TestCaseVersionRead)
def read_case_version(case_id: int, version_id: int, db: Session = Depends(get_db)) -> TestCaseVersionRead:
    _case_or_404(db, case_id)
    version = get_version(db, case_id, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case version not found.")
    return version


@router.post("/{case_id}/versions", response_model=TestCaseVersionRead, status_code=status.HTTP_201_CREATED)
def create_case_version(
    case_id: int,
    payload: TestCaseVersionCreate,
    db: Session = Depends(get_db),
) -> TestCaseVersionRead:
    case = _case_or_404(db, case_id)
    try:
        return create_version(db, case, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{case_id}/versions/{version_id}/activate", response_model=FunctionalTestCaseRead)
def activate_case_version(case_id: int, version_id: int, db: Session = Depends(get_db)) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id)
    version = get_version(db, case_id, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case version not found.")
    return activate_version(db, case, version)


@router.post("/{case_id}/dsl/validate", response_model=DslValidationResult)
def validate_case_dsl(case_id: int, payload: DslPayload, db: Session = Depends(get_db)) -> DslValidationResult:
    _case_or_404(db, case_id)
    return validate_dsl(payload.dsl_json)


@router.post("/{case_id}/dsl/format", response_model=dict[str, Any])
def format_case_dsl(case_id: int, payload: DslPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    _case_or_404(db, case_id)
    return format_dsl(payload.dsl_json)


@router.put("/{case_id}/dsl", response_model=FunctionalTestCaseRead)
def update_case_dsl_endpoint(case_id: int, payload: DslPayload, db: Session = Depends(get_db)) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id)
    try:
        return update_case_dsl(db, case, payload.dsl_json, payload.change_summary, payload.change_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{case_id}/analyze", response_model=AnalyzeResult)
def analyze_functional_case(case_id: int, payload: CaseAnalyzeRequest, db: Session = Depends(get_db)) -> AnalyzeResult:
    return analyze_case(db, _case_or_404(db, case_id), payload)


@router.post("/{case_id}/generate-dsl", response_model=dict[str, Any])
def generate_dsl_for_case(case_id: int, payload: CaseAnalyzeRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    return generate_case_dsl(db, _case_or_404(db, case_id), payload)


@router.post("/{case_id}/save-generated-dsl", response_model=FunctionalTestCaseRead)
def save_generated_dsl_for_case(
    case_id: int,
    payload: SaveGeneratedDslRequest,
    db: Session = Depends(get_db),
) -> FunctionalTestCaseRead:
    return save_generated_dsl(db, _case_or_404(db, case_id), payload)


@router.get("/{case_id}/runs", response_model=list[TestRunRead])
def read_case_runs(case_id: int, db: Session = Depends(get_db)) -> list[TestRunRead]:
    _case_or_404(db, case_id)
    return list_case_runs(db, case_id)


@router.get("/{case_id}/failure-samples", response_model=list[FailureSampleRead])
def read_case_failure_samples(case_id: int, db: Session = Depends(get_db)) -> list[FailureSampleRead]:
    _case_or_404(db, case_id)
    return list_case_failure_samples(db, case_id)


@router.get("/{case_id}/failure-analyses", response_model=list[FailureAnalysisRead])
def read_case_failure_analyses(case_id: int, db: Session = Depends(get_db)) -> list[FailureAnalysisRead]:
    _case_or_404(db, case_id)
    return list_case_failure_analyses(db, case_id)


@router.get("/{case_id}/fix-applications", response_model=list[FixApplicationRead])
def read_case_fix_applications(case_id: int, db: Session = Depends(get_db)) -> list[FixApplicationRead]:
    _case_or_404(db, case_id)
    return list_case_fix_applications(db, case_id)


def _case_or_404(db: Session, case_id: int):
    case = get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
    return case
