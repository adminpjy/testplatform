from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FunctionalTestCaseBase(BaseModel):
    case_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    source_type: str = Field(default="manual", max_length=64)
    natural_language_goal: str | None = None
    menu_path: str | None = Field(default=None, max_length=1024)
    business_intent: str | None = Field(default=None, max_length=255)
    inherit_project_account: bool = True
    account_id: int | None = None
    test_data_json: dict[str, Any] | None = None
    preconditions_json: dict[str, Any] | None = None
    success_criteria_json: dict[str, Any] | None = None
    settings_json: dict[str, Any] | None = None
    dsl_json: dict[str, Any] | None = None
    risk_level: str = "low"
    status: str = "draft"


class FunctionalTestCaseCreate(FunctionalTestCaseBase):
    case_code: str | None = Field(default=None, max_length=64)


class FunctionalTestCaseUpdate(BaseModel):
    case_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    source_type: str | None = Field(default=None, max_length=64)
    natural_language_goal: str | None = None
    menu_path: str | None = Field(default=None, max_length=1024)
    business_intent: str | None = Field(default=None, max_length=255)
    inherit_project_account: bool | None = None
    account_id: int | None = None
    test_data_json: dict[str, Any] | None = None
    preconditions_json: dict[str, Any] | None = None
    success_criteria_json: dict[str, Any] | None = None
    settings_json: dict[str, Any] | None = None
    dsl_json: dict[str, Any] | None = None
    risk_level: str | None = None
    status: str | None = None


class FunctionalTestCaseRead(FunctionalTestCaseBase):
    id: int
    project_id: int
    case_code: str | None = None
    current_version_id: int | None = None
    last_run_id: int | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    run_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TestCaseVersionCreate(BaseModel):
    version_label: str | None = None
    natural_language_goal: str | None = None
    dsl_json: dict[str, Any] | None = None
    test_data_json: dict[str, Any] | None = None
    preconditions_json: dict[str, Any] | None = None
    success_criteria_json: dict[str, Any] | None = None
    settings_json: dict[str, Any] | None = None
    change_type: str = "manual_edit"
    change_summary: str | None = None
    source_analysis_id: int | None = None
    source_run_id: int | None = None


class TestCaseVersionRead(TestCaseVersionCreate):
    id: int
    case_id: int
    version_no: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DslPayload(BaseModel):
    dsl_json: dict[str, Any]
    change_summary: str | None = None
    change_type: str = "manual_edit"


class DslValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    dsl_json: dict[str, Any] | None = None


class CaseAnalyzeRequest(BaseModel):
    instruction: str | None = None
    testData: dict[str, Any] | None = None
    stream: bool | None = None


class SaveGeneratedDslRequest(BaseModel):
    dsl_json: dict[str, Any]
    test_data_json: dict[str, Any] | None = None
    change_summary: str | None = None


class CaseRunCreate(BaseModel):
    caseVersionId: int | None = None
    accountId: int | None = None
    testDataOverride: dict[str, Any] = Field(default_factory=dict)
    settingsOverride: dict[str, Any] = Field(default_factory=dict)
    runName: str | None = None


class SaveRunAsCaseRequest(BaseModel):
    runId: int
    projectId: int
    caseName: str
    description: str | None = None


class FailureAnalysisRead(BaseModel):
    id: int
    project_id: int | None = None
    case_id: int | None = None
    case_version_id: int | None = None
    run_id: int
    failure_sample_id: int
    analysis_status: str
    failure_category: str | None = None
    root_cause: str | None = None
    confidence: float | None = None
    evidence_json: dict[str, Any] | None = None
    suggestions_json: dict[str, Any] | None = None
    recommended_actions_json: dict[str, Any] | None = None
    risk_level: str
    requires_human_review: bool
    error_summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FixApplicationRead(BaseModel):
    id: int
    project_id: int | None = None
    case_id: int | None = None
    run_id: int | None = None
    failure_analysis_id: int | None = None
    fix_type: str
    status: str
    before_snapshot_json: dict[str, Any] | None = None
    after_snapshot_json: dict[str, Any] | None = None
    created_case_version_id: int | None = None
    created_rule_draft_id: int | None = None
    verify_run_id: int | None = None
    reason: str | None = None
    defect_draft_json: dict[str, Any] | None = None
    created_at: datetime
    applied_at: datetime | None = None
    verified_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ApplySuggestionRequest(BaseModel):
    suggestionIndex: int = 0
    action: str
    confirm: bool = True


class ApplySuggestionResponse(BaseModel):
    fixApplicationId: int
    status: str
    createdCaseVersionId: int | None = None
    createdRuleDraftId: int | None = None
    message: str
