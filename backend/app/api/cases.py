from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import PlatformUser
from app.schemas.cases import (
    CaseAnalyzeRequest,
    CaseRunCreate,
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
from app.services.audit import log_audit
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
from app.services.permissions import require_project_permission
from app.services.test_run_execution import create_and_execute_case_run, rerun_case_latest, run_case_version

router = APIRouter()


@router.get("/{case_id}", response_model=FunctionalTestCaseRead)
def read_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FunctionalTestCaseRead:
    return _case_or_404(db, case_id, current_user, "view_cases")


@router.put("/{case_id}", response_model=FunctionalTestCaseRead)
def update_functional_case(
    case_id: int,
    payload: FunctionalTestCaseUpdate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id, current_user, "edit_cases")
    before = {"case_name": case.case_name, "status": case.status, "dsl_json": case.dsl_json}
    try:
        updated = update_case(db, case, payload, current_user)
        log_audit(
            db,
            current_user,
            "case_update",
            target_type="test_case",
            target_id=case_id,
            project_id=updated.project_id,
            case_id=case_id,
            before=before,
            after={"case_name": updated.case_name, "status": updated.status, "dsl_json": updated.dsl_json},
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_functional_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> None:
    case = _case_or_404(db, case_id, current_user, "delete_cases")
    project_id = case.project_id
    soft_delete_case(db, case)
    log_audit(db, current_user, "case_delete", target_type="test_case", target_id=case_id, project_id=project_id, case_id=case_id)


@router.post("/{case_id}/disable", response_model=FunctionalTestCaseRead)
def disable_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id, current_user, "edit_cases")
    updated = set_case_status(db, case, "disabled")
    log_audit(db, current_user, "case_disable", target_type="test_case", target_id=case_id, project_id=case.project_id, case_id=case_id)
    return updated


@router.post("/{case_id}/enable", response_model=FunctionalTestCaseRead)
def enable_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id, current_user, "edit_cases")
    updated = set_case_status(db, case, "active")
    log_audit(db, current_user, "case_enable", target_type="test_case", target_id=case_id, project_id=case.project_id, case_id=case_id)
    return updated


@router.post("/{case_id}/copy", response_model=FunctionalTestCaseRead, status_code=status.HTTP_201_CREATED)
def copy_functional_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FunctionalTestCaseRead:
    source = _case_or_404(db, case_id, current_user, "edit_cases")
    try:
        copied = copy_case(db, source, current_user)
        log_audit(
            db,
            current_user,
            "case_copy",
            target_type="test_case",
            target_id=copied.id,
            project_id=copied.project_id,
            case_id=copied.id,
            detail={"sourceCaseId": case_id},
        )
        return copied
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case code already exists.") from exc


@router.get("/{case_id}/versions", response_model=list[TestCaseVersionRead])
def read_case_versions(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[TestCaseVersionRead]:
    _case_or_404(db, case_id, current_user, "view_cases")
    return list_versions(db, case_id)


@router.get("/{case_id}/versions/{version_id}", response_model=TestCaseVersionRead)
def read_case_version(
    case_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestCaseVersionRead:
    _case_or_404(db, case_id, current_user, "view_cases")
    version = get_version(db, case_id, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case version not found.")
    return version


@router.post("/{case_id}/versions", response_model=TestCaseVersionRead, status_code=status.HTTP_201_CREATED)
def create_case_version(
    case_id: int,
    payload: TestCaseVersionCreate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestCaseVersionRead:
    case = _case_or_404(db, case_id, current_user, "edit_cases")
    try:
        version = create_version(db, case, payload)
        log_audit(
            db,
            current_user,
            "case_version_create",
            target_type="test_case_version",
            target_id=version.id,
            project_id=case.project_id,
            case_id=case_id,
            after={"version_no": version.version_no, "change_type": version.change_type},
        )
        return version
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{case_id}/versions/{version_id}/activate", response_model=FunctionalTestCaseRead)
def activate_case_version(
    case_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id, current_user, "edit_cases")
    version = get_version(db, case_id, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case version not found.")
    updated = activate_version(db, case, version)
    log_audit(
        db,
        current_user,
        "case_version_activate",
        target_type="test_case_version",
        target_id=version_id,
        project_id=case.project_id,
        case_id=case_id,
    )
    return updated


@router.post("/{case_id}/dsl/validate", response_model=DslValidationResult)
def validate_case_dsl(
    case_id: int,
    payload: DslPayload,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> DslValidationResult:
    _case_or_404(db, case_id, current_user, "view_cases")
    return validate_dsl(payload.dsl_json)


@router.post("/{case_id}/dsl/format", response_model=dict[str, Any])
def format_case_dsl(
    case_id: int,
    payload: DslPayload,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> dict[str, Any]:
    _case_or_404(db, case_id, current_user, "view_cases")
    return format_dsl(payload.dsl_json)


@router.put("/{case_id}/dsl", response_model=FunctionalTestCaseRead)
def update_case_dsl_endpoint(
    case_id: int,
    payload: DslPayload,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id, current_user, "edit_cases")
    before = {"dsl_json": case.dsl_json}
    try:
        updated = update_case_dsl(db, case, payload.dsl_json, payload.change_summary, payload.change_type, current_user)
        log_audit(
            db,
            current_user,
            "case_dsl_update",
            target_type="test_case",
            target_id=case_id,
            project_id=case.project_id,
            case_id=case_id,
            before=before,
            after={"dsl_json": updated.dsl_json, "change_type": payload.change_type},
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{case_id}/analyze", response_model=AnalyzeResult)
def analyze_functional_case(
    case_id: int,
    payload: CaseAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> AnalyzeResult:
    return analyze_case(db, _case_or_404(db, case_id, current_user, "edit_cases"), payload)


@router.post("/{case_id}/generate-dsl", response_model=dict[str, Any])
def generate_dsl_for_case(
    case_id: int,
    payload: CaseAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> dict[str, Any]:
    return generate_case_dsl(db, _case_or_404(db, case_id, current_user, "edit_cases"), payload)


@router.post("/{case_id}/save-generated-dsl", response_model=FunctionalTestCaseRead)
def save_generated_dsl_for_case(
    case_id: int,
    payload: SaveGeneratedDslRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FunctionalTestCaseRead:
    case = _case_or_404(db, case_id, current_user, "edit_cases")
    updated = save_generated_dsl(db, case, payload, current_user)
    log_audit(db, current_user, "case_generated_dsl_save", target_type="test_case", target_id=case_id, project_id=case.project_id, case_id=case_id)
    return updated


@router.get("/{case_id}/runs", response_model=list[TestRunRead])
def read_case_runs(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[TestRunRead]:
    _case_or_404(db, case_id, current_user, "view_runs")
    return list_case_runs(db, case_id)


@router.post("/{case_id}/runs", response_model=TestRunRead, status_code=status.HTTP_201_CREATED)
def create_run_from_case(
    case_id: int,
    payload: CaseRunCreate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestRunRead:
    case = _case_or_404(db, case_id, current_user, "run_case")
    try:
        run = create_and_execute_case_run(db, case_id, payload, actor_user_id=current_user.id)
        log_audit(db, current_user, "case_run_start", target_type="test_run", target_id=run.id, project_id=case.project_id, case_id=case_id, run_id=run.id)
        return run
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{case_id}/rerun-latest", response_model=TestRunRead, status_code=status.HTTP_201_CREATED)
def rerun_latest_case(
    case_id: int,
    payload: CaseRunCreate | None = None,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestRunRead:
    case = _case_or_404(db, case_id, current_user, "run_case")
    try:
        run = rerun_case_latest(db, case_id, payload, actor_user_id=current_user.id)
        log_audit(db, current_user, "case_rerun_latest", target_type="test_run", target_id=run.id, project_id=case.project_id, case_id=case_id, run_id=run.id)
        return run
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{case_id}/versions/{version_id}/run", response_model=TestRunRead, status_code=status.HTTP_201_CREATED)
def run_specific_case_version(
    case_id: int,
    version_id: int,
    payload: CaseRunCreate | None = None,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestRunRead:
    case = _case_or_404(db, case_id, current_user, "run_case")
    try:
        run = run_case_version(db, case_id, version_id, payload, actor_user_id=current_user.id)
        log_audit(
            db,
            current_user,
            "case_version_run",
            target_type="test_run",
            target_id=run.id,
            project_id=case.project_id,
            case_id=case_id,
            run_id=run.id,
            detail={"versionId": version_id},
        )
        return run
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{case_id}/failure-samples", response_model=list[FailureSampleRead])
def read_case_failure_samples(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[FailureSampleRead]:
    _case_or_404(db, case_id, current_user, "view_reports")
    return list_case_failure_samples(db, case_id)


@router.get("/{case_id}/failure-analyses", response_model=list[FailureAnalysisRead])
def read_case_failure_analyses(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[FailureAnalysisRead]:
    _case_or_404(db, case_id, current_user, "view_reports")
    return list_case_failure_analyses(db, case_id)


@router.get("/{case_id}/fix-applications", response_model=list[FixApplicationRead])
def read_case_fix_applications(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[FixApplicationRead]:
    _case_or_404(db, case_id, current_user, "view_reports")
    return list_case_fix_applications(db, case_id)


def _case_or_404(db: Session, case_id: int, current_user: PlatformUser, permission: str):
    case = get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
    require_project_permission(db, current_user, case.project_id, permission)
    return case
