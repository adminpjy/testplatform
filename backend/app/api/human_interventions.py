from math import ceil

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import HumanIntervention
from app.schemas.maturity import PageResponse
from app.schemas.test_runs import HumanInterventionRead
from app.services.human_interventions import list_human_interventions

router = APIRouter()


@router.get("", response_model=list[HumanInterventionRead])
def read_human_interventions(run_id: int | None = None, db: Session = Depends(get_db)) -> list[HumanInterventionRead]:
    return list_human_interventions(db, run_id=run_id)


@router.get("/paged", response_model=PageResponse)
def read_human_interventions_paged(
    page: int = 1,
    page_size: int = 20,
    run_id: int | None = None,
    db: Session = Depends(get_db),
) -> PageResponse:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 200))
    stmt = select(HumanIntervention)
    if run_id is not None:
        stmt = stmt.where(HumanIntervention.run_id == run_id)
    stmt = stmt.order_by(HumanIntervention.id.desc())
    total = int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    total_pages = ceil(total / page_size) if total else 0
    return PageResponse(
        items=[HumanInterventionRead.model_validate(item).model_dump(mode="json") for item in rows],
        page=page,
        pageSize=page_size,
        total=total,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


@router.delete("/{intervention_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_human_intervention(intervention_id: int, db: Session = Depends(get_db)) -> None:
    item = db.get(HumanIntervention, intervention_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Human intervention not found.")
    db.delete(item)
    db.commit()
