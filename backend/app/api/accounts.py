from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.projects import ProjectAccountRead, ProjectAccountUpdate
from app.services.projects import get_account, set_default_account, soft_delete_account, update_project_account

router = APIRouter()


@router.get("/{account_id}", response_model=ProjectAccountRead)
def read_account(account_id: int, db: Session = Depends(get_db)) -> ProjectAccountRead:
    account = get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    return account


@router.put("/{account_id}", response_model=ProjectAccountRead)
def update_account(
    account_id: int,
    payload: ProjectAccountUpdate,
    db: Session = Depends(get_db),
) -> ProjectAccountRead:
    account = get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    try:
        return update_project_account(db, account, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: Session = Depends(get_db)) -> None:
    account = get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    soft_delete_account(db, account)


@router.post("/{account_id}/set-default", response_model=ProjectAccountRead)
def set_project_default_account(account_id: int, db: Session = Depends(get_db)) -> ProjectAccountRead:
    account = get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    try:
        return set_default_account(db, account)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
