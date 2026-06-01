from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.enterprise import PrescanRequest, PrescanResponse, PrescanSessionRead
from app.services.prescan import get_prescan_session, run_project_prescan

router = APIRouter()


@router.post("/api/projects/{project_id}/prescan", response_model=PrescanResponse, status_code=status.HTTP_201_CREATED)
def create_project_prescan(
    project_id: int,
    payload: PrescanRequest,
    db: Session = Depends(get_db),
) -> PrescanResponse:
    try:
        return run_project_prescan(db, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/api/prescan-sessions/{session_id}", response_model=PrescanSessionRead)
def read_prescan_session(session_id: int, db: Session = Depends(get_db)) -> PrescanSessionRead:
    session = get_prescan_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescan session not found.")
    return session

