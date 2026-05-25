from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.projects import TestProjectCreate, TestProjectRead
from app.services.projects import create_project, get_project, list_projects

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
