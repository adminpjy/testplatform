from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TestProject
from app.schemas.projects import TestProjectCreate


def list_projects(db: Session) -> list[TestProject]:
    return list(db.scalars(select(TestProject).order_by(TestProject.id)).all())


def get_project(db: Session, project_id: int) -> TestProject | None:
    return db.get(TestProject, project_id)


def create_project(db: Session, payload: TestProjectCreate) -> TestProject:
    project = TestProject(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
