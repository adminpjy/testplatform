from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.test_runs import FailureSampleRead
from app.services.human_interventions import list_failure_samples

router = APIRouter()


@router.get("", response_model=list[FailureSampleRead])
def read_failure_samples(run_id: int | None = None, db: Session = Depends(get_db)) -> list[FailureSampleRead]:
    return list_failure_samples(db, run_id=run_id)
