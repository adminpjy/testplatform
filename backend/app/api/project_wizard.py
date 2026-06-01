from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.enterprise import (
    ImportBootstrapCasesRequest,
    ImportBootstrapCasesResponse,
    ProjectBootstrapPackageRead,
    ProjectWizardBootstrapRequest,
    ProjectWizardBootstrapResponse,
)
from app.services.project_wizard import bootstrap_project, get_bootstrap_package, import_bootstrap_cases

router = APIRouter()


@router.post("/bootstrap", response_model=ProjectWizardBootstrapResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_project_from_two_files(
    payload: ProjectWizardBootstrapRequest,
    db: Session = Depends(get_db),
) -> ProjectWizardBootstrapResponse:
    try:
        return bootstrap_project(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/bootstrap/{package_id}", response_model=ProjectBootstrapPackageRead)
def read_bootstrap_package(package_id: int, db: Session = Depends(get_db)) -> ProjectBootstrapPackageRead:
    package = get_bootstrap_package(db, package_id)
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bootstrap package not found.")
    return package


@router.post("/bootstrap/{package_id}/import-cases", response_model=ImportBootstrapCasesResponse)
def import_cases_from_bootstrap_package(
    package_id: int,
    payload: ImportBootstrapCasesRequest,
    db: Session = Depends(get_db),
) -> ImportBootstrapCasesResponse:
    try:
        return import_bootstrap_cases(db, package_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

