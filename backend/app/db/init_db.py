from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import engine
from app.models import TestProject


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_default_project(db: Session) -> None:
    has_project = db.query(TestProject.id).first()
    if has_project is not None:
        return

    project = TestProject(
        project_code="DEFAULT",
        name="默认测试项目",
        description="Initial project for enterprise MIS functional testing.",
        system_name="Default MIS",
        base_url="http://127.0.0.1:5174",
        login_url="http://127.0.0.1:5174/login",
        environment="local",
        status="active",
    )
    db.add(project)
    db.commit()


def init_db() -> None:
    create_tables()
    with Session(bind=engine) as db:
        ensure_default_project(db)
