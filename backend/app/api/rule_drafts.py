from math import ceil

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import FixApplication, RuleDraft
from app.schemas.abilities import AbilityRuleRead
from app.schemas.maturity import PageResponse
from app.schemas.test_runs import RuleDraftRead
from app.services.human_interventions import enable_rule_draft, list_rule_drafts

router = APIRouter()


@router.get("", response_model=list[RuleDraftRead])
def read_rule_drafts(
    draft_status: str | None = None,
    db: Session = Depends(get_db),
) -> list[RuleDraftRead]:
    return list_rule_drafts(db, draft_status=draft_status)


@router.get("/paged", response_model=PageResponse)
def read_rule_drafts_paged(
    page: int = 1,
    page_size: int = 20,
    draft_status: str | None = None,
    db: Session = Depends(get_db),
) -> PageResponse:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 200))
    stmt = select(RuleDraft)
    if draft_status:
        stmt = stmt.where(RuleDraft.status == draft_status)
    stmt = stmt.order_by(RuleDraft.id.desc())
    total = int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    total_pages = ceil(total / page_size) if total else 0
    return PageResponse(
        items=[RuleDraftRead.model_validate(item).model_dump(mode="json") for item in rows],
        page=page,
        pageSize=page_size,
        total=total,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


@router.post("/{draft_id}/enable", response_model=AbilityRuleRead)
def enable_draft_rule(draft_id: int, db: Session = Depends(get_db)) -> AbilityRuleRead:
    try:
        return enable_rule_draft(db, draft_id=draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule_draft(draft_id: int, db: Session = Depends(get_db)) -> None:
    draft = db.get(RuleDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule draft not found.")
    for fix in db.scalars(select(FixApplication).where(FixApplication.created_rule_draft_id == draft.id)).all():
        fix.created_rule_draft_id = None
        db.add(fix)
    db.delete(draft)
    db.commit()
