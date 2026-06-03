from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectAccountRead(BaseModel):
    id: int
    project_id: int | None = None
    account_name: str | None = None
    username: str
    role_name: str | None = None
    description: str | None = None
    allow_read: bool = True
    allow_write: bool = False
    allow_approval: bool = False
    allow_delete: bool = False
    is_default: bool = False
    status: str
    secret_ref: str | None = None
    has_password: bool = False
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TestProjectBase(BaseModel):
    project_code: str | None = Field(default=None, max_length=64)
    project_name: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    system_id: int | None = None
    system_name: str | None = Field(default=None, max_length=255)
    base_url: str | None = Field(default=None, max_length=1024)
    login_url: str | None = Field(default=None, max_length=1024)
    home_url: str | None = Field(default=None, max_length=1024)
    auth_type: str = Field(default="username_password", max_length=64)
    environment: str | None = Field(default="test", max_length=64)
    default_timeout_ms: int = Field(default=15000, ge=1000, le=300000)
    enable_trace_default: bool = True
    enable_screenshot_default: bool = True
    enable_dom_snapshot_default: bool = True
    enable_accessibility_snapshot_default: bool = True
    enable_vision_fallback_default: bool = False
    status: str = Field(default="active", max_length=32)

    @field_validator("base_url", "login_url", "home_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if not value:
            return value
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return value


class TestProjectCreate(TestProjectBase):
    project_name: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=255)


class TestProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    system_name: str | None = Field(default=None, max_length=255)
    base_url: str | None = Field(default=None, max_length=1024)
    login_url: str | None = Field(default=None, max_length=1024)
    home_url: str | None = Field(default=None, max_length=1024)
    auth_type: str | None = Field(default=None, max_length=64)
    environment: str | None = Field(default=None, max_length=64)
    default_timeout_ms: int | None = Field(default=None, ge=1000, le=300000)
    enable_trace_default: bool | None = None
    enable_screenshot_default: bool | None = None
    enable_dom_snapshot_default: bool | None = None
    enable_accessibility_snapshot_default: bool | None = None
    enable_vision_fallback_default: bool | None = None
    status: str | None = Field(default=None, max_length=32)

    @field_validator("base_url", "login_url", "home_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if not value:
            return value
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return value


class TestProjectRead(TestProjectBase):
    id: int
    project_code: str
    project_name: str | None = None
    name: str
    owner_user_id: int | None = None
    created_by_user_id: int | None = None
    default_account_id: int | None = None
    default_account: ProjectAccountRead | None = None
    case_count: int = 0
    account_count: int = 0
    last_run_status: str | None = None
    current_user_role: str | None = None
    current_user_permissions: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectAccountCreate(BaseModel):
    account_name: str | None = Field(default=None, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=4096)
    secret_ref: str | None = Field(default=None, max_length=512)
    role_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    allow_read: bool = True
    allow_write: bool = False
    allow_approval: bool = False
    allow_delete: bool = False
    is_default: bool = False
    status: str = Field(default="active", max_length=32)


class ProjectAccountUpdate(BaseModel):
    account_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=4096)
    secret_ref: str | None = Field(default=None, max_length=512)
    role_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    allow_read: bool | None = None
    allow_write: bool | None = None
    allow_approval: bool | None = None
    allow_delete: bool | None = None
    is_default: bool | None = None
    status: str | None = Field(default=None, max_length=32)


class CaseSummaryRead(BaseModel):
    id: int
    project_id: int
    case_code: str | None = None
    case_name: str
    description: str | None = None
    source_type: str
    natural_language_goal: str | None = None
    menu_path: str | None = None
    business_intent: str | None = None
    inherit_project_account: bool = True
    account_id: int | None = None
    status: str
    current_version_id: int | None = None
    last_run_id: int | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    run_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


JsonDict = dict[str, Any]
