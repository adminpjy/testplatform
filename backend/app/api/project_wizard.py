from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import PlatformUser
from app.schemas.enterprise import (
    ImportBootstrapCasesRequest,
    ImportBootstrapCasesResponse,
    ProjectBootstrapPackageRead,
    ProjectWizardBootstrapRequest,
    ProjectWizardBootstrapResponse,
)
from app.services.project_wizard import bootstrap_project, get_bootstrap_package, import_bootstrap_cases
from app.services.audit import log_audit
from app.services.permissions import require_project_permission

router = APIRouter()


@router.post("/bootstrap", response_model=ProjectWizardBootstrapResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_project_from_two_files(
    payload: ProjectWizardBootstrapRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> ProjectWizardBootstrapResponse:
    try:
        result = bootstrap_project(db, payload, current_user)
        log_audit(
            db,
            current_user,
            "project_wizard_bootstrap",
            target_type="project_bootstrap_package",
            target_id=result["package"].id,
            project_id=result["projectId"],
            detail={"draftCount": len(result.get("drafts") or [])},
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/bootstrap/{package_id}", response_model=ProjectBootstrapPackageRead)
def read_bootstrap_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> ProjectBootstrapPackageRead:
    package = get_bootstrap_package(db, package_id)
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bootstrap package not found.")
    require_project_permission(db, current_user, package.project_id, "view_cases")
    return package


@router.post("/bootstrap/{package_id}/import-cases", response_model=ImportBootstrapCasesResponse)
def import_cases_from_bootstrap_package(
    package_id: int,
    payload: ImportBootstrapCasesRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> ImportBootstrapCasesResponse:
    package = get_bootstrap_package(db, package_id)
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bootstrap package not found.")
    require_project_permission(db, current_user, package.project_id, "edit_cases")
    try:
        result = import_bootstrap_cases(db, package_id, payload, current_user)
        log_audit(
            db,
            current_user,
            "project_wizard_import_cases",
            target_type="project_bootstrap_package",
            target_id=package_id,
            project_id=result.projectId,
            detail={"importedCaseIds": result.importedCaseIds},
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
