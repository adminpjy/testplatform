from typing import Any

from pydantic import BaseModel, Field, field_validator


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
