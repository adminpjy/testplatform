from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AbilityRule
from app.schemas.abilities import RuleResolverMatch, RuleResolverRequest, RuleResolverResponse


def resolve_rule(db: Session, payload: RuleResolverRequest) -> RuleResolverResponse:
    stmt = select(AbilityRule).where(
        AbilityRule.status == "active",
        AbilityRule.production_enabled.is_(True),
    )
    if payload.rule_types:
        stmt = stmt.where(AbilityRule.rule_type.in_(payload.rule_types))
    rules = list(db.scalars(stmt).all())

    text = _request_text(payload)
    scored_matches: list[tuple[int, RuleResolverMatch]] = []
    for rule in rules:
        match = _score_rule(rule, payload, text)
        if match is not None:
            scored_matches.append((rule.priority, match))

    scored_matches.sort(key=lambda item: (-item[1].score, item[0], item[1].rule_code))
    matches = [match for _, match in scored_matches]
    selected = matches[0] if matches else None
    reason = selected.runtime_message if selected else "未命中可用规则。"
    return RuleResolverResponse(matchedRules=matches, selectedRule=selected, reason=reason)


def _score_rule(
    rule: AbilityRule,
    payload: RuleResolverRequest,
    request_text: str,
) -> RuleResolverMatch | None:
    config = rule.match_config_json or {}
    negative_phrases = _as_list(config.get("negative_actions"))
    negative_hits = _hits(negative_phrases, request_text)
    if negative_hits and config.get("negative_policy") == "exclude":
        return None

    score = 0.0
    reasons: list[str] = []

    trigger_hits = _hits(_as_list(config.get("trigger_phrases")), request_text)
    if trigger_hits:
        score += 0.35
        reasons.append("触发表达：" + "、".join(trigger_hits[:3]))

    positive_hits = _hits(_as_list(config.get("positive_actions")), request_text)
    if positive_hits:
        score += 0.25
        reasons.append("正向动作：" + "、".join(positive_hits[:3]))

    target_hits = _hits(_as_list(config.get("target_keywords")), request_text)
    if target_hits:
        score += 0.15
        reasons.append("目标命中：" + "、".join(target_hits[:3]))

    page_hits = _hits(_as_list(config.get("page_signals")), request_text)
    if page_hits:
        score += 0.10
        reasons.append("页面上下文：" + "、".join(page_hits[:3]))

    if payload.rule_types and rule.rule_type in payload.rule_types:
        score += 0.05
        reasons.append("规则类型匹配")

    if payload.business_intent and rule.intent and _contains_any(rule.intent, payload.business_intent):
        score += 0.10
        reasons.append("业务意图匹配")

    if negative_hits:
        score -= 0.30
        reasons.append("负向动作降权：" + "、".join(negative_hits[:3]))

    score = max(0.0, min(1.0, round(score, 4)))
    if score < rule.confidence_threshold:
        return None

    return RuleResolverMatch(
        id=rule.id,
        rule_code=rule.rule_code,
        rule_name=rule.rule_name,
        rule_type=rule.rule_type,
        score=score,
        reason="；".join(reasons) if reasons else "规则启用但缺少明确命中原因。",
        runtime_message=_runtime_message(rule),
        risk_level=rule.risk_level,
        production_enabled=rule.production_enabled,
    )


def _runtime_message(rule: AbilityRule) -> str:
    action_config = rule.action_config_json or {}
    configured_message = action_config.get("runtime_message")
    if configured_message:
        return str(configured_message)
    business_target = action_config.get("business_target") or rule.intent or rule.rule_name
    return f"命中规则 {rule.rule_code}：将按{business_target}执行。"


def _request_text(payload: RuleResolverRequest) -> str:
    parts = [
        payload.goal,
        payload.action,
        payload.target,
        payload.business_intent,
        _flatten(payload.page_context or {}),
    ]
    return " ".join(str(part).lower() for part in parts if part)


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value:
        return [str(value)]
    return []


def _hits(phrases: list[str], text: str) -> list[str]:
    return [phrase for phrase in phrases if phrase.lower() in text]


def _contains_any(left: str, right: str) -> bool:
    left_text = left.lower()
    right_text = right.lower()
    return left_text in right_text or right_text in left_text
