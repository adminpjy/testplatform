from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


JsonDict = dict[str, Any]


class PageResponse(BaseModel):
    items: list[JsonDict]
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class AssetCreate(BaseModel):
    assetName: str = Field(min_length=1, max_length=255)
    assetType: str = Field(min_length=1, max_length=64)
    projectId: int | None = None
    module: str | None = None
    tags: list[str] = Field(default_factory=list)
    owner: str | None = None
    riskLevel: str = "low"
    description: str | None = None
    content: JsonDict = Field(default_factory=dict)


class AssetUpdate(BaseModel):
    assetName: str | None = Field(default=None, min_length=1, max_length=255)
    module: str | None = None
    tags: list[str] | None = None
    owner: str | None = None
    status: str | None = None
    riskLevel: str | None = None
    description: str | None = None
    content: JsonDict | None = None
    changeSummary: str | None = None


class AssetRead(BaseModel):
    id: int
    asset_code: str
    asset_name: str
    asset_type: str
    project_id: int | None = None
    module: str | None = None
    tags_json: JsonDict | None = None
    status: str
    owner: str | None = None
    current_version_id: int | None = None
    latest_published_version_id: int | None = None
    risk_level: str
    description: str | None = None
    content_json: JsonDict | None = None
    metadata_json: JsonDict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetVersionRead(BaseModel):
    id: int
    asset_id: int
    version_no: int
    version_label: str | None = None
    status: str
    content_json: JsonDict | None = None
    diff_summary_json: JsonDict | None = None
    change_summary: str | None = None
    created_by: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenerateCasesRequest(BaseModel):
    projectId: int | None = None
    sourceText: str = ""
    strategy: str = "comprehensive"
    includeNegative: bool = True
    includeBoundary: bool = True
    includePermission: bool = True


class GeneratedCase(BaseModel):
    caseName: str
    module: str | None = None
    feature: str | None = None
    scenarioType: str
    naturalLanguageGoal: str
    testData: JsonDict = Field(default_factory=dict)
    expectedResult: str
    riskLevel: str = "low"
    coverage: list[str] = Field(default_factory=list)
    automationScore: float = 0.6


class GenerateCasesResponse(BaseModel):
    items: list[GeneratedCase]
    coverage: JsonDict
    summary: JsonDict


class DefectCreate(BaseModel):
    projectId: int | None = None
    caseId: int | None = None
    runId: int | None = None
    failureSampleId: int | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    defectType: str = "system_defect"
    severity: str = "medium"
    priority: str = "normal"
    assignee: str | None = None
    reproduceSteps: JsonDict = Field(default_factory=dict)
    evidence: JsonDict = Field(default_factory=dict)


class DefectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    defectType: str | None = None
    severity: str | None = None
    priority: str | None = None
    status: str | None = None
    assignee: str | None = None
    reproduceSteps: JsonDict | None = None
    evidence: JsonDict | None = None


class DefectRead(BaseModel):
    id: int
    defect_code: str
    project_id: int | None = None
    case_id: int | None = None
    run_id: int | None = None
    failure_sample_id: int | None = None
    title: str
    description: str | None = None
    defect_type: str
    severity: str
    priority: str
    status: str
    assignee: str | None = None
    reproduce_steps_json: JsonDict | None = None
    evidence_json: JsonDict | None = None
    external_ref_json: JsonDict | None = None
    dedup_key: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LearningItemCreate(BaseModel):
    projectId: int | None = None
    itemType: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    sourceType: str | None = None
    sourceId: int | None = None
    riskLevel: str = "medium"
    proposal: JsonDict = Field(default_factory=dict)


class LearningItemUpdate(BaseModel):
    itemType: str | None = Field(default=None, min_length=1, max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None
    riskLevel: str | None = None
    proposal: JsonDict | None = None
    validation: JsonDict | None = None


class LearningItemRead(BaseModel):
    id: int
    learning_code: str
    project_id: int | None = None
    item_type: str
    title: str
    status: str
    source_type: str | None = None
    source_id: int | None = None
    risk_level: str
    proposal_json: JsonDict | None = None
    validation_json: JsonDict | None = None
    audit_json: JsonDict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformUserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    displayName: str | None = None
    role: str = "tester"
    status: str = "active"


class PlatformUserUpdate(BaseModel):
    displayName: str | None = None
    role: str | None = None
    status: str | None = None


class PlatformUserRead(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: str
    status: str
    config_json: JsonDict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PluginCreate(BaseModel):
    pluginCode: str | None = None
    pluginName: str = Field(min_length=1, max_length=255)
    pluginType: str = Field(min_length=1, max_length=64)
    version: str = "1.0.0"
    status: str = "active"
    priority: int = 100
    configSchema: JsonDict = Field(default_factory=dict)
    config: JsonDict = Field(default_factory=dict)


class PluginUpdate(BaseModel):
    pluginName: str | None = Field(default=None, min_length=1, max_length=255)
    pluginType: str | None = Field(default=None, min_length=1, max_length=64)
    version: str | None = None
    status: str | None = None
    priority: int | None = None
    configSchema: JsonDict | None = None
    config: JsonDict | None = None


class PluginRead(BaseModel):
    id: int
    plugin_code: str
    plugin_name: str
    plugin_type: str
    version: str
    status: str
    priority: int
    config_schema_json: JsonDict | None = None
    config_json: JsonDict | None = None
    health_json: JsonDict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QualityOverview(BaseModel):
    projectId: int | None = None
    totals: JsonDict
    trends: list[JsonDict]
    modules: list[JsonDict]
    failures: list[JsonDict]
    recommendations: list[str]


class FailureSampleUpdate(BaseModel):
    status: str | None = None
    failureSummary: str | None = None
    aiAnalysis: JsonDict | None = None
    suggestedRule: JsonDict | None = None
