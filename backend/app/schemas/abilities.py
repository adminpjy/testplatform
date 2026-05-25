from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AbilityRuleBase(BaseModel):
    rule_code: str = Field(min_length=1, max_length=64)
    rule_name: str = Field(min_length=1, max_length=255)
    rule_type: str = Field(min_length=1, max_length=64)
    intent: str | None = None
    status: str = Field(default="draft", max_length=32)
    priority: int = 100
    match_config_json: dict[str, Any] | None = None
    action_config_json: dict[str, Any] | None = None
    success_criteria_json: dict[str, Any] | None = None
    fallback_strategies_json: dict[str, Any] | None = None
    risk_level: str = Field(default="medium", max_length=32)
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    source: str | None = Field(default=None, max_length=128)
    production_enabled: bool = False


class AbilityRuleCreate(AbilityRuleBase):
    pass


class AbilityRuleUpdate(BaseModel):
    rule_code: str | None = Field(default=None, min_length=1, max_length=64)
    rule_name: str | None = Field(default=None, min_length=1, max_length=255)
    rule_type: str | None = Field(default=None, min_length=1, max_length=64)
    intent: str | None = None
    status: str | None = Field(default=None, max_length=32)
    priority: int | None = None
    match_config_json: dict[str, Any] | None = None
    action_config_json: dict[str, Any] | None = None
    success_criteria_json: dict[str, Any] | None = None
    fallback_strategies_json: dict[str, Any] | None = None
    risk_level: str | None = Field(default=None, max_length=32)
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str | None = Field(default=None, max_length=128)
    production_enabled: bool | None = None


class AbilityRuleRead(AbilityRuleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleResolverRequest(BaseModel):
    project_id: int
    goal: str | None = None
    action: str | None = None
    target: str | None = None
    business_intent: str | None = None
    rule_types: list[str] | None = None
    page_context: dict[str, Any] | None = None


class RuleResolverMatch(BaseModel):
    id: int
    rule_code: str
    rule_name: str
    rule_type: str
    score: float
    reason: str
    runtime_message: str
    risk_level: str
    production_enabled: bool


class RuleResolverResponse(BaseModel):
    matchedRules: list[RuleResolverMatch]
    selectedRule: RuleResolverMatch | None
    reason: str
