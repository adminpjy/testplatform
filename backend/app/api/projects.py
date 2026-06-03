from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import PlatformUser
from app.schemas.auth import ProjectMemberCreate, ProjectMemberRead, ProjectMemberUpdate
from app.schemas.cases import FunctionalTestCaseCreate, FunctionalTestCaseRead
from app.schemas.projects import (
    ProjectAccountCreate,
    ProjectAccountRead,
    TestProjectCreate,
    TestProjectRead,
    TestProjectUpdate,
)
from app.services.cases import create_case, list_project_cases
from app.services.audit import log_audit
from app.services.permissions import require_project_permission
from app.services.projects import (
    create_project_member,
    delete_project_member,
    get_project_member,
    create_project,
    create_project_account,
    get_project,
    get_project_model,
    list_project_accounts,
    list_project_members,
    list_projects,
    soft_delete_project,
    update_project_member,
    update_project,
)

router = APIRouter()


@router.get("", response_model=list[TestProjectRead])
def read_projects(
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[TestProjectRead]:
    return list_projects(db, current_user)


@router.post("", response_model=TestProjectRead, status_code=status.HTTP_201_CREATED)
def create_test_project(
    payload: TestProjectCreate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestProjectRead:
    try:
        project = create_project(db, payload, current_user)
        log_audit(
            db,
            current_user,
            "project_create",
            target_type="test_project",
            target_id=project["id"],
            project_id=project["id"],
            after={"project_name": project.get("project_name"), "project_code": project.get("project_code")},
        )
        return project
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project code already exists.",
        ) from exc


@router.get("/{project_id}", response_model=TestProjectRead)
def read_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestProjectRead:
    project = get_project(db, project_id, current_user)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "view_project")
    return project


@router.put("/{project_id}", response_model=TestProjectRead)
def update_test_project(
    project_id: int,
    payload: TestProjectUpdate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestProjectRead:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "manage_project")
    before = {"project_name": project.project_name or project.name, "status": project.status}
    try:
        updated = update_project(db, project, payload, current_user)
        log_audit(
            db,
            current_user,
            "project_update",
            target_type="test_project",
            target_id=project_id,
            project_id=project_id,
            before=before,
            after={"project_name": updated.get("project_name"), "status": updated.get("status")},
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> None:
    _delete_project_or_404(project_id, db, current_user)


@router.post("/{project_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_project_fallback(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> None:
    _delete_project_or_404(project_id, db, current_user)


def _delete_project_or_404(project_id: int, db: Session, current_user: PlatformUser) -> None:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "manage_project")
    soft_delete_project(db, project)
    log_audit(db, current_user, "project_delete", target_type="test_project", target_id=project_id, project_id=project_id)


@router.get("/{project_id}/accounts", response_model=list[ProjectAccountRead])
def read_project_accounts(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[ProjectAccountRead]:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "view_project")
    return list_project_accounts(db, project_id)


@router.post("/{project_id}/accounts", response_model=ProjectAccountRead, status_code=status.HTTP_201_CREATED)
def create_account_for_project(
    project_id: int,
    payload: ProjectAccountCreate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> ProjectAccountRead:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "manage_accounts")
    account = create_project_account(db, project, payload)
    log_audit(
        db,
        current_user,
        "project_account_create",
        target_type="test_account",
        target_id=account.id,
        project_id=project_id,
        after={"username": account.username, "account_name": account.account_name},
    )
    return account


@router.get("/{project_id}/cases", response_model=list[FunctionalTestCaseRead])
def read_project_cases(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[FunctionalTestCaseRead]:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "view_cases")
    return list_project_cases(db, project_id)


@router.post("/{project_id}/cases", response_model=FunctionalTestCaseRead, status_code=status.HTTP_201_CREATED)
def create_case_for_project(
    project_id: int,
    payload: FunctionalTestCaseCreate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FunctionalTestCaseRead:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "edit_cases")
    try:
        case = create_case(db, project, payload, current_user)
        log_audit(
            db,
            current_user,
            "case_create",
            target_type="test_case",
            target_id=case.id,
            project_id=project_id,
            case_id=case.id,
            after={"case_name": case.case_name, "case_code": case.case_code},
        )
        return case
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case code already exists.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{project_id}/members", response_model=list[ProjectMemberRead])
def read_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[ProjectMemberRead]:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "view_project")
    return list_project_members(db, project_id)


@router.post("/{project_id}/members", response_model=ProjectMemberRead, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: int,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> ProjectMemberRead:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "manage_members")
    try:
        member = create_project_member(db, project, payload, actor=current_user)
        log_audit(
            db,
            current_user,
            "project_member_add",
            target_type="project_membership",
            target_id=member["id"],
            project_id=project_id,
            after={"username": member.get("username"), "role": member.get("role"), "permissions": member.get("permissions")},
        )
        return member
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.put("/{project_id}/members/{membership_id}", response_model=ProjectMemberRead)
def edit_project_member(
    project_id: int,
    membership_id: int,
    payload: ProjectMemberUpdate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> ProjectMemberRead:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "manage_members")
    membership = get_project_member(db, project_id, membership_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found.")
    before = {"role": membership.role, "permissions": membership.permissions_json, "status": membership.status}
    try:
        member = update_project_member(db, project, membership, payload)
        log_audit(
            db,
            current_user,
            "project_member_update",
            target_type="project_membership",
            target_id=membership_id,
            project_id=project_id,
            before=before,
            after={"role": member.get("role"), "permissions": member.get("permissions"), "status": member.get("status")},
        )
        return member
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{project_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> None:
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_project_permission(db, current_user, project_id, "manage_members")
    membership = get_project_member(db, project_id, membership_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found.")
    before = {"user_id": membership.user_id, "role": membership.role, "permissions": membership.permissions_json}
    try:
        delete_project_member(db, project, membership)
        log_audit(
            db,
            current_user,
            "project_member_delete",
            target_type="project_membership",
            target_id=membership_id,
            project_id=project_id,
            before=before,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
