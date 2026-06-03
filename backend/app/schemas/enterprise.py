from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.projects import ProjectAccountCreate, TestProjectCreate


JsonDict = dict[str, Any]


class BootstrapFilePayload(BaseModel):
    file_name: str = Field(min_length=1, max_length=512)
    role: str = Field(default="source", max_length=128)
    content: str = ""


class InitialCaseDraft(BaseModel):
    index: int
    caseName: str
    naturalLanguageGoal: str
    menuPath: str | None = None
    businessIntent: str | None = None
    testData: JsonDict = Field(default_factory=dict)
    riskLevel: str = "low"
    confidence: float = 0.55
    source: str = "bootstrap"


class ProjectWizardBootstrapRequest(BaseModel):
    project: TestProjectCreate
    account: ProjectAccountCreate | None = None
    files: list[BootstrapFilePayload] = Field(min_length=2, max_length=2)
    generatorResult: JsonDict | list[JsonDict] | None = None
    sourceType: str = Field(default="two_file_compare", max_length=64)


class ProjectBootstrapPackageRead(BaseModel):
    id: int
    project_id: int
    package_code: str
    status: str
    source_type: str
    file_a_name: str | None = None
    file_a_role: str | None = None
    file_b_name: str | None = None
    file_b_role: str | None = None
    draft_cases_json: JsonDict | None = None
    imported_case_ids_json: JsonDict | None = None
    summary_json: JsonDict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectWizardBootstrapResponse(BaseModel):
    projectId: int
    package: ProjectBootstrapPackageRead
    drafts: list[InitialCaseDraft]
    summary: JsonDict


class ImportBootstrapCasesRequest(BaseModel):
    draftIndexes: list[int] | None = None
    activate: bool = True


class ImportBootstrapCasesResponse(BaseModel):
    packageId: int
    projectId: int
    importedCaseIds: list[int]
    skippedIndexes: list[int] = Field(default_factory=list)
    summary: JsonDict


class PrescanRequest(BaseModel):
    caseIds: list[int] | None = None
    mode: str = Field(default="case_driven", max_length=64)
    dryRun: bool = True


class PrescanSessionRead(BaseModel):
    id: int
    project_id: int
    session_code: str
    status: str
    mode: str
    dry_run: bool
    case_ids_json: JsonDict | None = None
    plan_json: JsonDict | None = None
    findings_json: JsonDict | None = None
    rule_draft_ids_json: JsonDict | None = None
    ability_knowledge_ids_json: JsonDict | None = None
    enhanced_cases_json: JsonDict | None = None
    error_summary: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrescanResponse(BaseModel):
    session: PrescanSessionRead
    summary: JsonDict
    ruleDraftIds: list[int]
    abilityKnowledgeIds: list[int]
    enhancedCases: list[JsonDict]


class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    caseIds: list[int] | None = None
    settings: JsonDict = Field(default_factory=dict)


class CampaignStartRequest(BaseModel):
    accountId: int | None = None
    settingsOverride: JsonDict = Field(default_factory=dict)
    maxCases: int | None = Field(default=None, ge=1)


class CampaignCaseRead(BaseModel):
    id: int
    campaign_id: int
    project_id: int
    case_id: int
    case_version_id: int | None = None
    run_id: int | None = None
    order_index: int
    status: str
    failure_summary: str | None = None
    result_json: JsonDict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestCampaignRead(BaseModel):
    id: int
    project_id: int
    campaign_code: str
    name: str
    description: str | None = None
    status: str
    case_ids_json: JsonDict | None = None
    settings_json: JsonDict | None = None
    total_count: int
    queued_count: int
    running_count: int
    passed_count: int
    failed_count: int
    blocked_count: int
    summary_json: JsonDict | None = None
    created_by_user_id: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    cases: list[CampaignCaseRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CampaignReportSummary(BaseModel):
    campaignId: int
    campaignCode: str
    projectId: int
    name: str
    status: str
    totals: JsonDict
    failures: list[JsonDict]
    runs: list[JsonDict]
    recommendations: list[str]


class MaintenanceFeedbackCreate(BaseModel):
    runId: int | None = None
    failureSampleId: int | None = None
    summary: str | None = None
    userNote: str | None = None


class MaintenanceFeedbackRead(BaseModel):
    id: int
    feedback_code: str
    project_id: int | None = None
    case_id: int | None = None
    run_id: int | None = None
    failure_sample_id: int | None = None
    status: str
    summary: str | None = None
    evidence_package_json: JsonDict | None = None
    artifact_paths_json: JsonDict | None = None
    maintainer_notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
