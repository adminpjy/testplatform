from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EnvironmentName = Literal["dev", "test", "uat", "preprod", "prod"]
AuthType = Literal["username_password", "sso", "token", "other"]


class TestAccountBase(BaseModel):
    environment: EnvironmentName = "test"
    username: str = Field(min_length=1, max_length=255)
    role_name: str | None = Field(default=None, max_length=255)
    allow_write: bool = False
    allow_approval: bool = False
    allow_delete: bool = False
    status: str = Field(default="active", max_length=32)
    expires_at: datetime | None = None


class TestAccountCreate(TestAccountBase):
    password: str | None = Field(default=None, max_length=4096)
    secret_ref: str | None = Field(default=None, max_length=512)


class TestAccountRead(TestAccountBase):
    id: int
    system_id: int | None = None
    secret_ref: str | None = None
    has_password: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestSystemBase(BaseModel):
    system_code: str = Field(min_length=1, max_length=64)
    system_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    base_url: str = Field(min_length=1, max_length=1024)
    login_url: str | None = Field(default=None, max_length=1024)
    home_url: str | None = Field(default=None, max_length=1024)
    environment: EnvironmentName = "test"
    auth_type: AuthType = "username_password"
    default_timeout_ms: int = Field(default=15000, ge=1000, le=300000)
    allow_write: bool = False
    allow_approval: bool = False
    allow_delete: bool = False
    status: str = Field(default="active", max_length=32)
    config_json: dict[str, Any] | None = None


class TestSystemCreate(TestSystemBase):
    default_account: TestAccountCreate | None = None


class TestSystemUpdate(BaseModel):
    system_code: str | None = Field(default=None, min_length=1, max_length=64)
    system_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=1024)
    login_url: str | None = Field(default=None, max_length=1024)
    home_url: str | None = Field(default=None, max_length=1024)
    environment: EnvironmentName | None = None
    auth_type: AuthType | None = None
    default_timeout_ms: int | None = Field(default=None, ge=1000, le=300000)
    allow_write: bool | None = None
    allow_approval: bool | None = None
    allow_delete: bool | None = None
    status: str | None = Field(default=None, max_length=32)
    config_json: dict[str, Any] | None = None
    default_account: TestAccountCreate | None = None


class TestSystemRead(TestSystemBase):
    id: int
    accounts: list[TestAccountRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SystemCheckResult(BaseModel):
    system_id: int
    check_type: str
    status: str
    http_status: int | None = None
    response_time_ms: int | None = None
    screenshot_path: str | None = None
    runtime_stream_path: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoginCheckRequest(BaseModel):
    account_id: int | None = None
    username: str | None = None
    password: str | None = None
