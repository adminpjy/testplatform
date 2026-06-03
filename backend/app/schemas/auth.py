from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(default="", max_length=4096)


class CurrentUserRead(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: str
    status: str
    permissions: dict[str, Any] = Field(default_factory=dict)
    navigation: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    token: str
    user: CurrentUserRead


class ProjectMemberRead(BaseModel):
    id: int
    project_id: int
    user_id: int
    username: str
    display_name: str | None = None
    role: str
    permissions: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime | None = None


class ProjectMemberCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    role: str = Field(default="testuser", max_length=64)
    permissions: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="active", max_length=32)


class ProjectMemberUpdate(BaseModel):
    role: str | None = Field(default=None, max_length=64)
    permissions: dict[str, Any] | None = None
    status: str | None = Field(default=None, max_length=32)
