from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import FailureSample
from app.schemas.cases import FailureAnalysisRead
from app.schemas.test_runs import FailureSampleRead
from app.services.failure_analysis_service import FailureAnalysisService
from app.services.human_interventions import list_failure_samples

router = APIRouter()


@router.get("", response_model=list[FailureSampleRead])
def read_failure_samples(run_id: int | None = None, db: Session = Depends(get_db)) -> list[FailureSampleRead]:
    return list_failure_samples(db, run_id=run_id)


@router.post("/{sample_id}/analyze", response_model=FailureAnalysisRead)
def analyze_failure_sample(sample_id: int, db: Session = Depends(get_db)) -> FailureAnalysisRead:
    sample = db.get(FailureSample, sample_id)
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failure sample not found.")
    try:
        return FailureAnalysisService().analyze_failure(db, sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
