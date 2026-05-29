from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cases import FunctionalTestCaseCreate, FunctionalTestCaseRead
from app.schemas.projects import (
    ProjectAccountCreate,
    ProjectAccountRead,
    TestProjectCreate,
    TestProjectRead,
    TestProjectUpdate,
)
from app.services.cases import create_case, list_project_cases
from app.services.projects import (
    create_project,
    create_project_account,
    get_project,
    get_project_model,
    list_project_accounts,
    list_projects,
    soft_delete_project,
    update_project,
)

router = APIRouter()


@router.get("", response_model=list[TestProjectRead])
def read_projects(db: Session = Depends(get_db)) -> list[TestProjectRead]:
    return list_projects(db)


@router.post("", response_model=TestProjectRead, status_code=status.HTTP_201_CREATED)
def create_test_project(
    payload: TestProjectCreate, db: Session = Depends(get_db)
) -> TestProjectRead:
    try:
        return create_project(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project code already exists.",
        ) from exc


@router.get("/{project_id}", response_model=TestProjectRead)
def read_project(project_id: int, db: Session = Depends(get_db)) -> TestProjectRead:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


@router.put("/{project_id}", response_model=TestProjectRead)
def update_test_project(
    project_id: int,
    payload: TestProjectUpdate,
    db: Session = Depends(get_db),
) -> TestProjectRead:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    try:
        return update_project(db, project, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_project(project_id: int, db: Session = Depends(get_db)) -> None:
    _delete_project_or_404(project_id, db)


@router.post("/{project_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_project_fallback(project_id: int, db: Session = Depends(get_db)) -> None:
    _delete_project_or_404(project_id, db)


def _delete_project_or_404(project_id: int, db: Session) -> None:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    soft_delete_project(db, project)


@router.get("/{project_id}/accounts", response_model=list[ProjectAccountRead])
def read_project_accounts(project_id: int, db: Session = Depends(get_db)) -> list[ProjectAccountRead]:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return list_project_accounts(db, project_id)


@router.post("/{project_id}/accounts", response_model=ProjectAccountRead, status_code=status.HTTP_201_CREATED)
def create_account_for_project(
    project_id: int,
    payload: ProjectAccountCreate,
    db: Session = Depends(get_db),
) -> ProjectAccountRead:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return create_project_account(db, project, payload)


@router.get("/{project_id}/cases", response_model=list[FunctionalTestCaseRead])
def read_project_cases(project_id: int, db: Session = Depends(get_db)) -> list[FunctionalTestCaseRead]:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return list_project_cases(db, project_id)


@router.post("/{project_id}/cases", response_model=FunctionalTestCaseRead, status_code=status.HTTP_201_CREATED)
def create_case_for_project(
    project_id: int,
    payload: FunctionalTestCaseCreate,
    db: Session = Depends(get_db),
) -> FunctionalTestCaseRead:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    try:
        return create_case(db, project, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case code already exists.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
