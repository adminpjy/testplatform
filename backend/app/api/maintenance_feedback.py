from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.enterprise import MaintenanceFeedbackCreate, MaintenanceFeedbackRead
from app.services.maintenance_feedback import create_maintenance_feedback, get_maintenance_feedback, list_maintenance_feedback

router = APIRouter()


@router.post("/api/maintenance-feedback", response_model=MaintenanceFeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(
    payload: MaintenanceFeedbackCreate,
    db: Session = Depends(get_db),
) -> MaintenanceFeedbackRead:
    try:
        return create_maintenance_feedback(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/maintenance-feedback", response_model=list[MaintenanceFeedbackRead])
def read_feedback_list(project_id: int | None = None, db: Session = Depends(get_db)) -> list[MaintenanceFeedbackRead]:
    return list_maintenance_feedback(db, project_id=project_id)


@router.get("/api/maintenance-feedback/{feedback_id}", response_model=MaintenanceFeedbackRead)
def read_feedback(feedback_id: int, db: Session = Depends(get_db)) -> MaintenanceFeedbackRead:
    feedback = get_maintenance_feedback(db, feedback_id)
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance feedback not found.")
    return feedback

