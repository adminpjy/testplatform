from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.test_runs import HumanInterventionRead
from app.services.human_interventions import list_human_interventions

router = APIRouter()


@router.get("", response_model=list[HumanInterventionRead])
def read_human_interventions(run_id: int | None = None, db: Session = Depends(get_db)) -> list[HumanInterventionRead]:
    return list_human_interventions(db, run_id=run_id)
