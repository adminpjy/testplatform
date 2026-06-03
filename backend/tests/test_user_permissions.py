from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.models import PlatformUser
from app.schemas.auth import ProjectMemberCreate
from app.schemas.projects import TestProjectCreate as ProjectCreateSchema
from app.services.auth import ensure_default_admin
from app.services.permissions import project_permissions
from app.services.projects import create_project, create_project_member, get_project_model, list_project_members, list_projects


def test_project_creator_becomes_project_owner() -> None:
    session = _session()
    admin = ensure_default_admin(session)

    created = create_project(session, ProjectCreateSchema(project_name="权限项目", base_url="https://example.test/"), admin)
    project = get_project_model(session, int(created["id"]))
    members = list_project_members(session, int(created["id"]))

    assert project is not None
    assert project.owner_user_id == admin.id
    assert members[0]["username"] == "admin"
    assert members[0]["role"] == "owner"
    assert members[0]["permissions"]["manage_members"] is True


def test_member_only_sees_authorized_projects_and_default_permissions() -> None:
    session = _session()
    admin = ensure_default_admin(session)
    first = create_project(session, ProjectCreateSchema(project_name="授权项目", base_url="https://one.example.test/"), admin)
    create_project(session, ProjectCreateSchema(project_name="未授权项目", base_url="https://two.example.test/"), admin)

    member = PlatformUser(username="tester-a", display_name="测试用户A", role="testuser", status="active")
    session.add(member)
    session.commit()
    session.refresh(member)
    project = get_project_model(session, int(first["id"]))
    assert project is not None

    create_project_member(session, project, ProjectMemberCreate(username="tester-a", role="testuser"), actor=admin)

    visible_projects = list_projects(session, member)
    permissions = project_permissions(session, member, project.id)

    assert [item["id"] for item in visible_projects] == [project.id]
    assert permissions["view_project"] is True
    assert permissions["run_case"] is True
    assert permissions["run_campaign"] is False
    assert permissions["manage_members"] is False


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)
