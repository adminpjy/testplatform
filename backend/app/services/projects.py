from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PlatformUser, ProjectMembership, TestAccount, TestCase, TestProject, TestRun
from app.schemas.auth import ProjectMemberCreate, ProjectMemberUpdate
from app.schemas.projects import (
    ProjectAccountCreate,
    ProjectAccountUpdate,
    TestProjectCreate,
    TestProjectUpdate,
)
from app.services.auth import normalize_user_role
from app.services.permissions import (
    DEFAULT_TESTUSER_PERMISSIONS,
    OWNER_PERMISSIONS,
    accessible_project_ids,
    ensure_project_owner_membership,
    is_admin,
    membership_for_project,
    normalize_permissions,
    normalize_project_role,
    project_permissions,
)
from app.utils.secrets import encrypt_secret


def list_projects(db: Session, user: PlatformUser | None = None) -> list[dict[str, Any]]:
    query = select(TestProject).where(TestProject.deleted_at.is_(None), TestProject.status != "deleted")
    if user is not None:
        ids = accessible_project_ids(db, user)
        if ids is not None:
            if not ids:
                return []
            query = query.where(TestProject.id.in_(ids))
    projects = db.scalars(query.order_by(TestProject.id.desc())).all()
    return [_project_payload(db, project, user=user) for project in projects]


def get_project(db: Session, project_id: int, user: PlatformUser | None = None) -> dict[str, Any] | None:
    project = _get_project_model(db, project_id)
    if project is None:
        return None
    return _project_payload(db, project, user=user)


def get_project_model(db: Session, project_id: int) -> TestProject | None:
    return _get_project_model(db, project_id)


def create_project(db: Session, payload: TestProjectCreate, user: PlatformUser | None = None) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    _validate_project_urls(data)
    project_name = (data.get("project_name") or data.get("name") or "").strip()
    if not project_name:
        raise ValueError("project_name is required.")
    project = TestProject(
        project_code=data.get("project_code") or _project_code(),
        project_name=project_name,
        name=project_name,
        description=data.get("description"),
        system_id=data.get("system_id"),
        system_name=data.get("system_name"),
        base_url=data.get("base_url"),
        login_url=data.get("login_url"),
        home_url=data.get("home_url"),
        auth_type=data.get("auth_type") or "username_password",
        environment=data.get("environment") or "test",
        default_timeout_ms=data.get("default_timeout_ms") or 15000,
        enable_trace_default=bool(data.get("enable_trace_default", True)),
        enable_screenshot_default=bool(data.get("enable_screenshot_default", True)),
        enable_dom_snapshot_default=bool(data.get("enable_dom_snapshot_default", True)),
        enable_accessibility_snapshot_default=bool(data.get("enable_accessibility_snapshot_default", True)),
        enable_vision_fallback_default=bool(data.get("enable_vision_fallback_default", False)),
        status=data.get("status") or "active",
        owner_user_id=user.id if user else None,
        created_by_user_id=user.id if user else None,
    )
    db.add(project)
    db.flush()
    if user is not None:
        ensure_project_owner_membership(db, project, user)
    db.commit()
    db.refresh(project)
    return _project_payload(db, project, user=user)


def update_project(db: Session, project: TestProject, payload: TestProjectUpdate, user: PlatformUser | None = None) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    _validate_project_urls(data)
    project_name = data.pop("project_name", None)
    name = data.pop("name", None)
    if project_name is not None or name is not None:
        final_name = (project_name or name or "").strip()
        if not final_name:
            raise ValueError("project_name cannot be empty.")
        project.project_name = final_name
        project.name = final_name
    for field_name, value in data.items():
        setattr(project, field_name, value)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_payload(db, project, user=user)


def soft_delete_project(db: Session, project: TestProject) -> None:
    project.status = "deleted"
    project.deleted_at = datetime.now(timezone.utc)
    db.add(project)
    db.commit()


def list_project_accounts(db: Session, project_id: int) -> list[TestAccount]:
    return list(
        db.scalars(
            select(TestAccount)
            .where(
                TestAccount.project_id == project_id,
                TestAccount.deleted_at.is_(None),
                TestAccount.status != "deleted",
            )
            .order_by(TestAccount.is_default.desc(), TestAccount.id.desc())
        ).all()
    )


def get_account(db: Session, account_id: int) -> TestAccount | None:
    account = db.get(TestAccount, account_id)
    if account is None or account.deleted_at is not None or account.status == "deleted":
        return None
    return account


def create_project_account(db: Session, project: TestProject, payload: ProjectAccountCreate) -> TestAccount:
    data = payload.model_dump(exclude_unset=True)
    account = TestAccount(
        project_id=project.id,
        system_id=project.system_id,
        environment=project.environment or "test",
        account_name=data.get("account_name"),
        username=data["username"],
        password_encrypted=encrypt_secret(data.get("password")),
        secret_ref=data.get("secret_ref"),
        role_name=data.get("role_name"),
        description=data.get("description"),
        allow_read=bool(data.get("allow_read", True)),
        allow_write=bool(data.get("allow_write", False)),
        allow_approval=bool(data.get("allow_approval", False)),
        allow_delete=bool(data.get("allow_delete", False)),
        is_default=bool(data.get("is_default", False)),
        status=data.get("status") or "active",
    )
    if account.is_default or _active_account_count(db, project.id) == 0:
        _clear_default_accounts(db, project.id)
        account.is_default = True
    db.add(account)
    db.flush()
    if account.is_default:
        project.default_account_id = account.id
        db.add(project)
    db.commit()
    db.refresh(account)
    return account


def update_project_account(db: Session, account: TestAccount, payload: ProjectAccountUpdate) -> TestAccount:
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    is_default = data.pop("is_default", None)
    if password:
        account.password_encrypted = encrypt_secret(password)
    for field_name, value in data.items():
        setattr(account, field_name, value)
    if is_default is not None:
        if is_default:
            set_default_account(db, account)
        else:
            account.is_default = False
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def soft_delete_account(db: Session, account: TestAccount) -> None:
    account.status = "deleted"
    account.is_default = False
    account.deleted_at = datetime.now(timezone.utc)
    project = db.get(TestProject, account.project_id) if account.project_id else None
    if project and project.default_account_id == account.id:
        project.default_account_id = None
        db.add(project)
    db.add(account)
    db.commit()


def set_default_account(db: Session, account: TestAccount) -> TestAccount:
    if not account.project_id:
        raise ValueError("Account is not attached to a project.")
    _clear_default_accounts(db, account.project_id)
    account.is_default = True
    project = db.get(TestProject, account.project_id)
    if project:
        project.default_account_id = account.id
        db.add(project)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def list_project_members(db: Session, project_id: int) -> list[dict[str, Any]]:
    memberships = list(
        db.scalars(
            select(ProjectMembership)
            .where(ProjectMembership.project_id == project_id)
            .order_by(ProjectMembership.role.desc(), ProjectMembership.id.desc())
        ).all()
    )
    return [_membership_payload(db, membership) for membership in memberships]


def create_project_member(
    db: Session,
    project: TestProject,
    payload: ProjectMemberCreate,
    actor: PlatformUser | None = None,
) -> dict[str, Any]:
    username = payload.username.strip()
    if not username:
        raise ValueError("username is required.")
    user = db.scalars(select(PlatformUser).where(PlatformUser.username == username)).first()
    member_role = normalize_project_role(payload.role)
    if user is None:
        user = PlatformUser(
            username=username,
            display_name=payload.display_name or username,
            role=member_role if member_role == "owner" else "testuser",
            status=payload.status or "active",
        )
        db.add(user)
        db.flush()
    else:
        if payload.display_name is not None:
            user.display_name = payload.display_name
        if normalize_user_role(user.role) != "admin" and member_role == "owner":
            user.role = "owner"
        db.add(user)

    membership = db.scalars(
        select(ProjectMembership).where(ProjectMembership.project_id == project.id, ProjectMembership.user_id == user.id)
    ).first()
    permissions = normalize_permissions(member_role, payload.permissions)
    if membership is None:
        membership = ProjectMembership(
            project_id=project.id,
            user_id=user.id,
            role=member_role,
            permissions_json=permissions,
            status=payload.status or "active",
            created_by_user_id=actor.id if actor else None,
        )
    else:
        membership.role = member_role
        membership.permissions_json = permissions
        membership.status = payload.status or "active"
    db.add(membership)
    if member_role == "owner" and project.owner_user_id is None:
        project.owner_user_id = user.id
        db.add(project)
    db.commit()
    db.refresh(membership)
    return _membership_payload(db, membership)


def update_project_member(
    db: Session,
    project: TestProject,
    membership: ProjectMembership,
    payload: ProjectMemberUpdate,
) -> dict[str, Any]:
    if membership.project_id != project.id:
        raise ValueError("Project member not found.")
    role = normalize_project_role(payload.role or membership.role)
    if payload.role is not None:
        membership.role = role
    if payload.permissions is not None:
        membership.permissions_json = normalize_permissions(role, payload.permissions)
    elif payload.role is not None:
        membership.permissions_json = normalize_permissions(role, membership.permissions_json)
    if payload.status is not None:
        membership.status = payload.status
    db.add(membership)
    member_user = db.get(PlatformUser, membership.user_id)
    if member_user is not None and normalize_user_role(member_user.role) != "admin" and role == "owner":
        member_user.role = "owner"
        db.add(member_user)
    db.commit()
    db.refresh(membership)
    return _membership_payload(db, membership)


def get_project_member(db: Session, project_id: int, membership_id: int) -> ProjectMembership | None:
    return db.scalars(
        select(ProjectMembership).where(ProjectMembership.id == membership_id, ProjectMembership.project_id == project_id)
    ).first()


def delete_project_member(db: Session, project: TestProject, membership: ProjectMembership) -> None:
    if project.owner_user_id == membership.user_id and membership.role == "owner":
        raise ValueError("项目 owner 不能从成员列表删除。请先转移 owner。")
    db.delete(membership)
    db.commit()


def _get_project_model(db: Session, project_id: int) -> TestProject | None:
    project = db.get(TestProject, project_id)
    if project is None or project.deleted_at is not None or project.status == "deleted":
        return None
    return project


def _project_payload(db: Session, project: TestProject, user: PlatformUser | None = None) -> dict[str, Any]:
    default_account = db.get(TestAccount, project.default_account_id) if project.default_account_id else None
    if default_account is not None and (default_account.deleted_at is not None or default_account.status == "deleted"):
        default_account = None
    last_run_status = db.scalar(
        select(TestRun.status).where(TestRun.project_id == project.id).order_by(TestRun.id.desc()).limit(1)
    )
    permissions = project_permissions(db, user, project.id) if user is not None else None
    membership = membership_for_project(db, user.id, project.id) if user is not None and not is_admin(user) else None
    current_role = "admin" if user is not None and is_admin(user) else None
    if current_role is None and user is not None and project.owner_user_id == user.id:
        current_role = "owner"
    if current_role is None and membership is not None:
        current_role = normalize_project_role(membership.role)
    return {
        "id": project.id,
        "project_code": project.project_code,
        "project_name": project.project_name or project.name,
        "name": project.name,
        "description": project.description,
        "system_id": project.system_id,
        "system_name": project.system_name,
        "base_url": project.base_url,
        "login_url": project.login_url,
        "home_url": project.home_url,
        "auth_type": project.auth_type,
        "environment": project.environment,
        "default_timeout_ms": project.default_timeout_ms,
        "owner_user_id": project.owner_user_id,
        "created_by_user_id": project.created_by_user_id,
        "enable_trace_default": project.enable_trace_default,
        "enable_screenshot_default": project.enable_screenshot_default,
        "enable_dom_snapshot_default": project.enable_dom_snapshot_default,
        "enable_accessibility_snapshot_default": project.enable_accessibility_snapshot_default,
        "enable_vision_fallback_default": project.enable_vision_fallback_default,
        "status": project.status,
        "default_account_id": project.default_account_id,
        "default_account": default_account,
        "account_count": _active_account_count(db, project.id),
        "case_count": db.scalar(
            select(func.count(TestCase.id)).where(
                TestCase.project_id == project.id,
                TestCase.deleted_at.is_(None),
                TestCase.status != "deleted",
            )
        )
        or 0,
        "last_run_status": last_run_status,
        "current_user_role": current_role,
        "current_user_permissions": permissions,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "deleted_at": project.deleted_at,
    }


def _membership_payload(db: Session, membership: ProjectMembership) -> dict[str, Any]:
    user = db.get(PlatformUser, membership.user_id)
    permissions = normalize_permissions(membership.role, membership.permissions_json)
    return {
        "id": membership.id,
        "project_id": membership.project_id,
        "user_id": membership.user_id,
        "username": user.username if user else "",
        "display_name": user.display_name if user else None,
        "role": normalize_project_role(membership.role),
        "permissions": permissions,
        "status": membership.status,
        "created_at": membership.created_at,
        "updated_at": membership.updated_at,
    }


def _clear_default_accounts(db: Session, project_id: int) -> None:
    accounts = db.scalars(
        select(TestAccount).where(
            TestAccount.project_id == project_id,
            TestAccount.deleted_at.is_(None),
            TestAccount.status != "deleted",
        )
    ).all()
    for account in accounts:
        account.is_default = False
        db.add(account)


def _active_account_count(db: Session, project_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(TestAccount.id)).where(
                TestAccount.project_id == project_id,
                TestAccount.deleted_at.is_(None),
                TestAccount.status != "deleted",
            )
        )
        or 0
    )


def _validate_project_urls(data: dict[str, Any]) -> None:
    for key in ["base_url", "login_url", "home_url"]:
        value = data.get(key)
        if not value:
            continue
        parsed = urlparse(str(value))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{key} must be a valid http/https URL.")


def _project_code() -> str:
    return f"PRJ-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
