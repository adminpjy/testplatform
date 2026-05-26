from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.systems import (
    LoginCheckRequest,
    SystemCheckResult,
    TestSystemCreate,
    TestSystemRead,
    TestSystemUpdate,
)
from app.services.systems import (
    check_connectivity,
    check_login,
    create_system,
    get_system,
    list_systems,
    update_system,
)

router = APIRouter()


@router.get("", response_model=list[TestSystemRead])
def read_systems(db: Session = Depends(get_db)) -> list[TestSystemRead]:
    return list_systems(db)


@router.post("", response_model=TestSystemRead, status_code=status.HTTP_201_CREATED)
def create_test_system(payload: TestSystemCreate, db: Session = Depends(get_db)) -> TestSystemRead:
    try:
        return create_system(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System code already exists.") from exc


@router.get("/{system_id}", response_model=TestSystemRead)
def read_system(system_id: int, db: Session = Depends(get_db)) -> TestSystemRead:
    return _get_system_or_404(db, system_id)


@router.put("/{system_id}", response_model=TestSystemRead)
def update_test_system(
    system_id: int,
    payload: TestSystemUpdate,
    db: Session = Depends(get_db),
) -> TestSystemRead:
    try:
        return update_system(db, _get_system_or_404(db, system_id), payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System code already exists.") from exc


@router.post("/{system_id}/check-connectivity", response_model=SystemCheckResult)
def check_system_connectivity(system_id: int, db: Session = Depends(get_db)) -> SystemCheckResult:
    return check_connectivity(db, _get_system_or_404(db, system_id))


@router.post("/{system_id}/check-login", response_model=SystemCheckResult)
def check_system_login(
    system_id: int,
    payload: LoginCheckRequest | None = None,
    db: Session = Depends(get_db),
) -> SystemCheckResult:
    try:
        return check_login(db, _get_system_or_404(db, system_id), payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _get_system_or_404(db: Session, system_id: int):
    system = get_system(db, system_id)
    if system is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test system not found.")
    return system
