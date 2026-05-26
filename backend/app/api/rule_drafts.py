from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.abilities import AbilityRuleRead
from app.schemas.test_runs import RuleDraftRead
from app.services.human_interventions import enable_rule_draft, list_rule_drafts

router = APIRouter()


@router.get("", response_model=list[RuleDraftRead])
def read_rule_drafts(
    draft_status: str | None = None,
    db: Session = Depends(get_db),
) -> list[RuleDraftRead]:
    return list_rule_drafts(db, draft_status=draft_status)


@router.post("/{draft_id}/enable", response_model=AbilityRuleRead)
def enable_draft_rule(draft_id: int, db: Session = Depends(get_db)) -> AbilityRuleRead:
    try:
        return enable_rule_draft(db, draft_id=draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
