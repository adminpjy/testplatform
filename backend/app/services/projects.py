from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TestAccount, TestCase, TestProject, TestRun
from app.schemas.projects import (
    ProjectAccountCreate,
    ProjectAccountUpdate,
    TestProjectCreate,
    TestProjectUpdate,
)
from app.utils.secrets import encrypt_secret


def list_projects(db: Session) -> list[dict[str, Any]]:
    projects = db.scalars(
        select(TestProject)
        .where(TestProject.deleted_at.is_(None), TestProject.status != "deleted")
        .order_by(TestProject.id.desc())
    ).all()
    return [_project_payload(db, project) for project in projects]


def get_project(db: Session, project_id: int) -> dict[str, Any] | None:
    project = _get_project_model(db, project_id)
    if project is None:
        return None
    return _project_payload(db, project)


def get_project_model(db: Session, project_id: int) -> TestProject | None:
    return _get_project_model(db, project_id)


def create_project(db: Session, payload: TestProjectCreate) -> dict[str, Any]:
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
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_payload(db, project)


def update_project(db: Session, project: TestProject, payload: TestProjectUpdate) -> dict[str, Any]:
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
    return _project_payload(db, project)


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


def _get_project_model(db: Session, project_id: int) -> TestProject | None:
    project = db.get(TestProject, project_id)
    if project is None or project.deleted_at is not None or project.status == "deleted":
        return None
    return project


def _project_payload(db: Session, project: TestProject) -> dict[str, Any]:
    default_account = db.get(TestAccount, project.default_account_id) if project.default_account_id else None
    if default_account is not None and (default_account.deleted_at is not None or default_account.status == "deleted"):
        default_account = None
    last_run_status = db.scalar(
        select(TestRun.status).where(TestRun.project_id == project.id).order_by(TestRun.id.desc()).limit(1)
    )
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
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "deleted_at": project.deleted_at,
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
