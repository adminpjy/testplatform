from datetime import datetime
from typing import Any

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
    "click_table_row_action",
    "business_goal",
}


class NaturalLanguageTestRequest(BaseModel):
    project_id: int | None = None
    instruction: str = Field(min_length=1)
    base_url: str | None = None
    credentials: dict[str, Any] | None = None
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
    settings: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)

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
    case_id: int | None = None
    instruction: str | None = None
    base_url: str | None = None
    dsl_json: TestCaseDSL | None = None


class TestRunRead(BaseModel):
    id: int
    run_code: str
    project_id: int
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
