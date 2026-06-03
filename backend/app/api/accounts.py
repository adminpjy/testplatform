from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import PlatformUser
from app.schemas.projects import ProjectAccountRead, ProjectAccountUpdate
from app.services.audit import log_audit
from app.services.permissions import require_project_permission
from app.services.projects import get_account, set_default_account, soft_delete_account, update_project_account

router = APIRouter()


@router.get("/{account_id}", response_model=ProjectAccountRead)
def read_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> ProjectAccountRead:
    account = get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    if account.project_id is not None:
        require_project_permission(db, current_user, account.project_id, "view_project")
    return account


@router.put("/{account_id}", response_model=ProjectAccountRead)
def update_account(
    account_id: int,
    payload: ProjectAccountUpdate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> ProjectAccountRead:
    account = get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    if account.project_id is not None:
        require_project_permission(db, current_user, account.project_id, "manage_accounts")
    before = {"username": account.username, "account_name": account.account_name, "is_default": account.is_default}
    try:
        updated = update_project_account(db, account, payload)
        log_audit(
            db,
            current_user,
            "project_account_update",
            target_type="test_account",
            target_id=account_id,
            project_id=updated.project_id,
            before=before,
            after={"username": updated.username, "account_name": updated.account_name, "is_default": updated.is_default},
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> None:
    account = get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    project_id = account.project_id
    if project_id is not None:
        require_project_permission(db, current_user, project_id, "manage_accounts")
    soft_delete_account(db, account)
    log_audit(db, current_user, "project_account_delete", target_type="test_account", target_id=account_id, project_id=project_id)


@router.post("/{account_id}/set-default", response_model=ProjectAccountRead)
def set_project_default_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> ProjectAccountRead:
    account = get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    if account.project_id is not None:
        require_project_permission(db, current_user, account.project_id, "manage_accounts")
    try:
        updated = set_default_account(db, account)
        log_audit(db, current_user, "project_account_set_default", target_type="test_account", target_id=account_id, project_id=updated.project_id)
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
