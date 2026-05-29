from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cases import FixApplicationRead
from app.schemas.test_runs import TestRunRead
from app.services.fix_application_service import get_fix_application, verify_fix_application

router = APIRouter()


@router.get("/{fix_id}", response_model=FixApplicationRead)
def read_fix_application(fix_id: int, db: Session = Depends(get_db)) -> FixApplicationRead:
    fix = get_fix_application(db, fix_id)
    if fix is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fix application not found.")
    return fix


@router.post("/{fix_id}/verify-run", response_model=TestRunRead, status_code=status.HTTP_201_CREATED)
def create_fix_verify_run(fix_id: int, db: Session = Depends(get_db)) -> TestRunRead:
    try:
        return verify_fix_application(db, fix_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
