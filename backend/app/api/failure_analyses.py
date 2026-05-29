from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cases import FailureAnalysisRead
from app.services.failure_analysis_service import get_failure_analysis

router = APIRouter()


@router.get("/{analysis_id}", response_model=FailureAnalysisRead)
def read_failure_analysis(analysis_id: int, db: Session = Depends(get_db)) -> FailureAnalysisRead:
    analysis = get_failure_analysis(db, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failure analysis not found.")
    return analysis
