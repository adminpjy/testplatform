from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.abilities.base_pack import BASE_ABILITY_RULES
from app.models import AbilityRule
from app.schemas.abilities import AbilityRuleCreate, AbilityRuleUpdate


def ensure_base_ability_rules(db: Session) -> None:
    existing_rules = {rule.rule_code: rule for rule in db.scalars(select(AbilityRule)).all()}
    for rule_data in BASE_ABILITY_RULES:
        existing = existing_rules.get(rule_data["rule_code"])
        if existing is not None:
            if rule_data.get("source") == "builtin":
                existing.source = "builtin"
                existing.status = "active"
                existing.production_enabled = True
                db.add(existing)
            continue
        db.add(AbilityRule(**rule_data))
    db.commit()


def list_rules(
    db: Session,
    *,
    rule_type: str | None = None,
    rule_status: str | None = None,
    production_enabled: bool | None = None,
) -> list[AbilityRule]:
    stmt = select(AbilityRule)
    if rule_type:
        stmt = stmt.where(AbilityRule.rule_type == rule_type)
    if rule_status:
        stmt = stmt.where(AbilityRule.status == rule_status)
    if production_enabled is not None:
        stmt = stmt.where(AbilityRule.production_enabled == production_enabled)
    stmt = stmt.order_by(AbilityRule.rule_type, AbilityRule.priority, AbilityRule.id)
    return list(db.scalars(stmt).all())


def get_rule(db: Session, rule_id: int) -> AbilityRule | None:
    return db.get(AbilityRule, rule_id)


def create_rule(db: Session, payload: AbilityRuleCreate) -> AbilityRule:
    rule = AbilityRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, rule: AbilityRule, payload: AbilityRuleUpdate) -> AbilityRule:
    update_data: dict[str, Any] = payload.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(rule, field_name, value)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def set_rule_enabled(db: Session, rule: AbilityRule, enabled: bool) -> AbilityRule:
    rule.production_enabled = enabled
    rule.status = "active" if enabled else "disabled"
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule
