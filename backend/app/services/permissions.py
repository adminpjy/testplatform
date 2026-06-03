from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PlatformUser, ProjectMembership, TestProject
from app.services.auth import normalize_user_role

ADMIN_ROLE = "admin"
OWNER_ROLE = "owner"
TESTUSER_ROLE = "testuser"

PROJECT_PERMISSION_KEYS = [
    "view_project",
    "manage_project",
    "manage_members",
    "manage_accounts",
    "view_cases",
    "edit_cases",
    "delete_cases",
    "run_case",
    "run_campaign",
    "view_runs",
    "view_reports",
]

OWNER_PERMISSIONS = {key: True for key in PROJECT_PERMISSION_KEYS}
DEFAULT_TESTUSER_PERMISSIONS = {
    "view_project": True,
    "manage_project": False,
    "manage_members": False,
    "manage_accounts": False,
    "view_cases": True,
    "edit_cases": False,
    "delete_cases": False,
    "run_case": True,
    "run_campaign": False,
    "view_runs": True,
    "view_reports": True,
}


def is_admin(user: PlatformUser | None) -> bool:
    return normalize_user_role(user.role if user else None) == ADMIN_ROLE


def normalize_project_role(role: str | None) -> str:
    value = normalize_user_role(role)
    if value == ADMIN_ROLE:
        return OWNER_ROLE
    return value


def normalize_permissions(role: str | None, permissions: dict[str, Any] | None = None) -> dict[str, bool]:
    base = dict(OWNER_PERMISSIONS if normalize_project_role(role) == OWNER_ROLE else DEFAULT_TESTUSER_PERMISSIONS)
    for key, value in (permissions or {}).items():
        if key in base:
            base[key] = bool(value)
    return base


def membership_for_project(db: Session, user_id: int, project_id: int) -> ProjectMembership | None:
    return db.scalars(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
            ProjectMembership.status == "active",
        )
    ).first()


def project_permissions(db: Session, user: PlatformUser, project_id: int) -> dict[str, bool]:
    if is_admin(user):
        return dict(OWNER_PERMISSIONS)
    project = db.get(TestProject, project_id)
    if project is not None and project.owner_user_id == user.id:
        return dict(OWNER_PERMISSIONS)
    membership = membership_for_project(db, user.id, project_id)
    if membership is None:
        return {}
    return normalize_permissions(membership.role, membership.permissions_json)


def can_access_project(db: Session, user: PlatformUser, project_id: int, permission: str = "view_project") -> bool:
    permissions = project_permissions(db, user, project_id)
    return bool(permissions.get(permission))


def require_project_permission(db: Session, user: PlatformUser, project_id: int, permission: str) -> None:
    if can_access_project(db, user, project_id, permission):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"当前用户没有该项目的权限：{permission}",
    )


def require_admin(user: PlatformUser) -> None:
    if is_admin(user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前功能仅管理员可使用。")


def accessible_project_ids(db: Session, user: PlatformUser) -> list[int] | None:
    if is_admin(user):
        return None
    owned_ids = list(
        db.scalars(
            select(TestProject.id).where(
                TestProject.owner_user_id == user.id,
                TestProject.deleted_at.is_(None),
                TestProject.status != "deleted",
            )
        ).all()
    )
    member_ids = list(
        db.scalars(
            select(ProjectMembership.project_id).where(
                ProjectMembership.user_id == user.id,
                ProjectMembership.status == "active",
            )
        ).all()
    )
    return sorted(set(owned_ids + member_ids))


def ensure_project_owner_membership(db: Session, project: TestProject, user: PlatformUser) -> ProjectMembership:
    if project.owner_user_id is None:
        project.owner_user_id = user.id
        db.add(project)
    membership = db.scalars(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project.id,
            ProjectMembership.user_id == user.id,
        )
    ).first()
    if membership is None:
        membership = ProjectMembership(
            project_id=project.id,
            user_id=user.id,
            role=OWNER_ROLE,
            permissions_json=dict(OWNER_PERMISSIONS),
            status="active",
            created_by_user_id=user.id,
        )
        db.add(membership)
    else:
        membership.role = OWNER_ROLE
        membership.permissions_json = dict(OWNER_PERMISSIONS)
        membership.status = "active"
        db.add(membership)
    return membership
