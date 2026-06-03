from math import ceil

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_admin_user, get_current_user
from app.models import FailureSample
from app.schemas.cases import FailureAnalysisRead
from app.schemas.failure_workflow import FailureContextRead, FailureSolutionGenerateRequest, FailureSolutionRead
from app.schemas.maturity import FailureSampleUpdate, PageResponse
from app.schemas.test_runs import FailureSampleRead
from app.models import PlatformUser
from app.services.failure_analysis_service import FailureAnalysisService
from app.services.failure_workflow import generate_failure_solution, get_failure_context, list_failure_solutions
from app.services.human_interventions import list_failure_samples
from app.services import maturity

router = APIRouter()


@router.get("", response_model=list[FailureSampleRead])
def read_failure_samples(run_id: int | None = None, db: Session = Depends(get_db)) -> list[FailureSampleRead]:
    return list_failure_samples(db, run_id=run_id)


@router.get("/paged", response_model=PageResponse)
def read_failure_samples_paged(
    page: int = 1,
    page_size: int = 20,
    run_id: int | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
) -> PageResponse:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 200))
    stmt = select(FailureSample)
    if run_id is not None:
        stmt = stmt.where(FailureSample.run_id == run_id)
    if status_filter:
        stmt = stmt.where(FailureSample.status == status_filter)
    stmt = stmt.order_by(FailureSample.id.desc())
    total = int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    total_pages = ceil(total / page_size) if total else 0
    return PageResponse(
        items=[FailureSampleRead.model_validate(item).model_dump(mode="json") for item in rows],
        page=page,
        pageSize=page_size,
        total=total,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


@router.put("/{sample_id}", response_model=FailureSampleRead)
def update_failure_sample(sample_id: int, payload: FailureSampleUpdate, db: Session = Depends(get_db)) -> FailureSampleRead:
    try:
        return maturity.update_failure_sample(db, sample_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_failure_sample(sample_id: int, db: Session = Depends(get_db)) -> None:
    try:
        maturity.delete_failure_sample(db, sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{sample_id}/analyze", response_model=FailureAnalysisRead)
def analyze_failure_sample(sample_id: int, db: Session = Depends(get_db)) -> FailureAnalysisRead:
    sample = db.get(FailureSample, sample_id)
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failure sample not found.")
    try:
        return FailureAnalysisService().analyze_failure(db, sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{sample_id}/context", response_model=FailureContextRead)
def read_failure_context(
    sample_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FailureContextRead:
    try:
        return get_failure_context(db, sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{sample_id}/solutions", response_model=list[FailureSolutionRead])
def read_failure_solutions(
    sample_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[FailureSolutionRead]:
    try:
        return list_failure_solutions(db, sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{sample_id}/solutions/generate", response_model=FailureSolutionRead)
def generate_failure_solution_from_sample(
    sample_id: int,
    payload: FailureSolutionGenerateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_admin_user),
) -> FailureSolutionRead:
    try:
        return generate_failure_solution(db, sample_id, actor=current_user, force=bool(payload.force if payload else False))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
