from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import FailureSample
from app.schemas.test_runs import FailureSampleRead
from app.services.human_interventions import list_failure_samples

router = APIRouter()


@router.get("", response_model=list[FailureSampleRead])
def read_failure_samples(run_id: int | None = None, db: Session = Depends(get_db)) -> list[FailureSampleRead]:
    return list_failure_samples(db, run_id=run_id)


@router.post("/{sample_id}/analyze", response_model=FailureSampleRead)
def analyze_failure_sample(sample_id: int, db: Session = Depends(get_db)) -> FailureSampleRead:
    sample = db.get(FailureSample, sample_id)
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failure sample not found.")
    sample.ai_analysis_json = {
        "status": "analyzed",
        "summary": sample.failure_summary,
        "suggested_next_step": "review_or_create_human_intervention",
    }
    sample.status = "analyzed"
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample
