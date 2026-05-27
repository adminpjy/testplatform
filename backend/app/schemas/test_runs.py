from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_DSL_ACTIONS = {
    "open_url",
    "input",
    "click",
    "navigate_menu",
    "wait_for_text",
    "assert_text_exists",
    "assert_text_not_exists",
    "assert_url_contains",
    "select",
    "upload_file",
    "wait",
    "confirm_dialog",
    "query_table",
    "query_table_count",
    "click_table_row_action",
    "for_each_table_row",
    "process_table_rows",
    "open_table_row",
    "open_row_link_or_detail",
    "wait_for_dialog",
    "close_dialog_by_common_controls",
    "continue_until_all_rows_processed",
    "summary_assert",
    "assert_result",
    "business_goal",
    "auto_fill_form",
    "fill_form",
    "navigate_path",
}


class NaturalLanguageTestRequest(BaseModel):
    project_id: int | None = None
    system_id: int | None = None
    instruction: str = Field(min_length=1)
    base_url: str | None = None
    credentials: dict[str, Any] | None = None
    testData: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    stream: bool | None = None


class AnalyzeResult(BaseModel):
    readyToExecute: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    understoodGoal: str = ""
    missingFields: list[str] = Field(default_factory=list)
    clarifyingQuestions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    riskLevel: str = "low"
    normalizedInstruction: str = ""


class TestCaseDSL(BaseModel):
    caseName: str = ""
    baseUrl: str = ""
    credentials: dict[str, Any] = Field(default_factory=dict)
    testData: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    missingFields: list[str] = Field(default_factory=list)
    clarifyingQuestions: list[str] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def validate_step_actions(cls, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        invalid = [
            str(step.get("action"))
            for step in steps
            if not isinstance(step, dict) or step.get("action") not in ALLOWED_DSL_ACTIONS
        ]
        if invalid:
            raise ValueError(f"Unsupported DSL action(s): {', '.join(invalid)}")
        return steps


class TestRunCreate(BaseModel):
    project_id: int
    system_id: int | None = None
    case_id: int | None = None
    instruction: str | None = None
    base_url: str | None = None
    dsl_json: TestCaseDSL | None = None


class TestRunRead(BaseModel):
    id: int
    run_code: str
    project_id: int
    system_id: int | None = None
    case_id: int | None = None
    instruction: str | None = None
    base_url: str | None = None
    status: str
    current_phase: str | None = None
    dsl_json: dict[str, Any] | None = None
    summary_json: dict[str, Any] | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestStepRunRead(BaseModel):
    id: int
    run_id: int
    step_id: str | None = None
    step_name: str | None = None
    action: str | None = None
    target: str | None = None
    status: str
    locator_strategy: str | None = None
    element_ref: str | None = None
    confidence: float | None = None
    reason: str | None = None
    screenshot_path: str | None = None
    error_summary: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TestArtifactRead(BaseModel):
    id: int
    run_id: int
    step_id: int | None = None
    artifact_type: str
    file_path: str
    metadata_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuntimeMessageRead(BaseModel):
    id: int
    run_id: int | None = None
    type: str
    phase: str | None = None
    content: str | None = None
    method: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FailureSampleRead(BaseModel):
    id: int
    run_id: int
    step_id: int | None = None
    failure_type: str | None = None
    failure_summary: str | None = None
    screenshot_path: str | None = None
    dom_snapshot_path: str | None = None
    accessibility_snapshot_path: str | None = None
    locator_debug_path: str | None = None
    runtime_stream_path: str | None = None
    execution_trace_path: str | None = None
    report_path: str | None = None
    ai_analysis_json: dict[str, Any] | None = None
    suggested_rule_json: dict[str, Any] | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


InterventionAction = Literal[
    "click",
    "input",
    "select",
    "choose_radio",
    "close_dialog",
    "confirm_dialog",
    "wait",
    "retry_step",
    "assert_text_exists",
    "assert_url_contains",
]


class InterventionPlanStep(BaseModel):
    action: InterventionAction
    target: str | None = None
    value: str | None = None
    reason: str | None = None


class InterventionPlan(BaseModel):
    summary: str
    steps: list[InterventionPlanStep] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class HumanInterventionCreate(BaseModel):
    user_instruction: str = Field(min_length=1, max_length=4000)


class HumanInterventionRead(BaseModel):
    id: int
    run_id: int
    step_id: int | None = None
    user_instruction: str | None = None
    llm_plan_json: dict[str, Any] | None = None
    execution_result_json: dict[str, Any] | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleDraftRead(BaseModel):
    id: int
    source_type: str
    source_id: int | None = None
    rule_type: str
    rule_name: str
    proposed_content_json: dict[str, Any] | None = None
    reason: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
