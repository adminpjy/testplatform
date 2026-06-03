from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FailureContextRead(BaseModel):
    failureSampleId: int
    context: dict[str, Any]
    latestAnalysis: dict[str, Any] | None = None
    latestSolution: dict[str, Any] | None = None
    latestValidation: dict[str, Any] | None = None
    maintenanceResponse: dict[str, Any] | None = None


class FailureSolutionGenerateRequest(BaseModel):
    force: bool = False


class FailureSolutionUpdate(BaseModel):
    rootCause: str | None = None
    solutionSummary: str | None = None
    generalizedPattern: dict[str, Any] | None = None
    strategy: dict[str, Any] | None = None
    suggestedRule: dict[str, Any] | None = None
    validationPlan: dict[str, Any] | None = None
    userReply: str | None = None
    internalNotes: str | None = None
    status: str | None = None
    adminAdjustment: dict[str, Any] | None = None


class FailureSolutionRead(BaseModel):
    id: int
    solution_code: str
    failure_sample_id: int
    failure_analysis_id: int | None = None
    pattern_id: int | None = None
    project_id: int | None = None
    case_id: int | None = None
    run_id: int | None = None
    rule_draft_id: int | None = None
    root_cause: str | None = None
    solution_summary: str | None = None
    generalized_pattern_json: dict[str, Any] | None = None
    strategy_json: dict[str, Any] | None = None
    suggested_rule_json: dict[str, Any] | None = None
    validation_plan_json: dict[str, Any] | None = None
    context_snapshot_json: dict[str, Any] | None = None
    user_reply: str | None = None
    internal_notes: str | None = None
    admin_adjustment_json: dict[str, Any] | None = None
    status: str
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleValidationRequest(BaseModel):
    validationType: str = Field(default="evidence_static_precheck")
    sampleIds: list[int] = Field(default_factory=list)


class RuleValidationRead(BaseModel):
    id: int
    validation_code: str
    solution_id: int | None = None
    rule_draft_id: int | None = None
    ability_rule_id: int | None = None
    project_id: int | None = None
    case_id: int | None = None
    run_id: int | None = None
    validation_type: str
    sample_ids_json: dict[str, Any] | None = None
    status: str
    passed_count: int
    failed_count: int
    false_positive_count: int
    result_json: dict[str, Any] | None = None
    report_json: dict[str, Any] | None = None
    created_by_user_id: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleDraftFromSolutionResponse(BaseModel):
    ruleDraftId: int
    status: str
    message: str


class PublishSolutionRuleResponse(BaseModel):
    abilityRuleId: int
    ruleDraftId: int
    status: str
    message: str


class MaintenanceResponseRead(BaseModel):
    id: int
    response_code: str
    failure_sample_id: int | None = None
    solution_id: int | None = None
    validation_id: int | None = None
    project_id: int | None = None
    case_id: int | None = None
    run_id: int | None = None
    submitted_by_user_id: int | None = None
    handled_by_user_id: int | None = None
    status: str
    root_cause: str | None = None
    fix_summary: str | None = None
    validation_result: str | None = None
    user_reply: str | None = None
    internal_notes: str | None = None
    evidence_summary_json: dict[str, Any] | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
