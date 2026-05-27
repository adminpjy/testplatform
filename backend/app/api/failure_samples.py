from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import FailureSample
from app.schemas.test_runs import FailureSampleRead
from app.services.failure_analyzer import FailureAnalyzer
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
    analysis = FailureAnalyzer().recovery_policy.analyze_failure(
        error_summary=sample.failure_summary,
        action=(sample.ai_analysis_json or {}).get("stepAction") if isinstance(sample.ai_analysis_json, dict) else None,
        target=(sample.ai_analysis_json or {}).get("target") if isinstance(sample.ai_analysis_json, dict) else None,
        failure_type=sample.failure_type,
        details=(sample.ai_analysis_json or {}).get("details") if isinstance(sample.ai_analysis_json, dict) else None,
    )
    sample.failure_type = str(analysis.get("failureType") or sample.failure_type)
    sample.ai_analysis_json = {
        "status": "analyzed",
        "summary": analysis.get("summary") or sample.failure_summary,
        "failureType": analysis.get("failureType"),
        "category": analysis.get("category"),
        "attemptedStrategies": analysis.get("attemptedStrategies"),
        "suggestedRecovery": analysis.get("suggestedRecovery"),
        "canIntervene": analysis.get("canIntervene"),
        "canGenerateRuleDraft": analysis.get("canGenerateRuleDraft"),
        "visionFallback": analysis.get("visionFallback"),
        "suggested_next_step": "review_or_create_human_intervention",
    }
    sample.status = "analyzed"
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample
