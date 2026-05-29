from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=512)
    doc_type: str = Field(default="txt", max_length=64)
    content: str = ""


class DocumentSourceRead(BaseModel):
    id: int
    project_id: int
    file_name: str
    file_path: str
    doc_type: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractedCaseDraftRead(BaseModel):
    id: int
    project_id: int
    document_id: int
    case_name: str
    natural_language_goal: str | None = None
    menu_path: str | None = None
    test_data_json: dict[str, Any] | None = None
    suggested_account_role: str | None = None
    confidence: float | None = None
    status: str
    created_case_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractDraftUpdate(BaseModel):
    case_name: str | None = Field(default=None, max_length=255)
    natural_language_goal: str | None = None
    menu_path: str | None = Field(default=None, max_length=1024)
    test_data_json: dict[str, Any] | None = None
    suggested_account_role: str | None = Field(default=None, max_length=255)
