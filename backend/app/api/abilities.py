from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AbilityKnowledge
from app.schemas.abilities import (
    AbilityKnowledgeRead,
    AbilityRuleCreate,
    AbilityRuleRead,
    AbilityRuleUpdate,
    RuleResolverRequest,
    RuleResolverResponse,
)
from app.services.abilities import create_rule, get_rule, list_rules, set_rule_enabled, update_rule
from app.services.rule_resolver import resolve_rule

router = APIRouter()


@router.get("/rules", response_model=list[AbilityRuleRead])
def read_rules(
    rule_type: str | None = None,
    rule_status: str | None = None,
    production_enabled: bool | None = None,
    db: Session = Depends(get_db),
) -> list[AbilityRuleRead]:
    return list_rules(
        db,
        rule_type=rule_type,
        rule_status=rule_status,
        production_enabled=production_enabled,
    )


@router.post("/rules", response_model=AbilityRuleRead, status_code=status.HTTP_201_CREATED)
def create_ability_rule(payload: AbilityRuleCreate, db: Session = Depends(get_db)) -> AbilityRuleRead:
    try:
        return create_rule(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rule code already exists.",
        ) from exc


@router.put("/rules/{rule_id}", response_model=AbilityRuleRead)
def update_ability_rule(
    rule_id: int,
    payload: AbilityRuleUpdate,
    db: Session = Depends(get_db),
) -> AbilityRuleRead:
    rule = _get_rule_or_404(db, rule_id)
    try:
        return update_rule(db, rule, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rule code already exists.",
        ) from exc


@router.post("/rules/{rule_id}/enable", response_model=AbilityRuleRead)
def enable_ability_rule(rule_id: int, db: Session = Depends(get_db)) -> AbilityRuleRead:
    return set_rule_enabled(db, _get_rule_or_404(db, rule_id), True)


@router.post("/rules/{rule_id}/disable", response_model=AbilityRuleRead)
def disable_ability_rule(rule_id: int, db: Session = Depends(get_db)) -> AbilityRuleRead:
    return set_rule_enabled(db, _get_rule_or_404(db, rule_id), False)


@router.post("/resolve", response_model=RuleResolverResponse)
def resolve_ability_rule(
    payload: RuleResolverRequest,
    db: Session = Depends(get_db),
) -> RuleResolverResponse:
    return resolve_rule(db, payload)


@router.get("/knowledge", response_model=list[AbilityKnowledgeRead])
def read_ability_knowledge(
    system_id: int | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[AbilityKnowledgeRead]:
    from sqlalchemy import select

    stmt = select(AbilityKnowledge).order_by(AbilityKnowledge.id.desc())
    if system_id is not None:
        stmt = stmt.where(AbilityKnowledge.system_id == system_id)
    if project_id is not None:
        stmt = stmt.where(AbilityKnowledge.project_id == project_id)
    return list(db.scalars(stmt).all())


def _get_rule_or_404(db: Session, rule_id: int):
    rule = get_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ability rule not found.")
    return rule
