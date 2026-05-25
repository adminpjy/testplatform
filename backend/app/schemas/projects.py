from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TestProjectBase(BaseModel):
    project_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    system_name: str | None = Field(default=None, max_length=255)
    base_url: str | None = Field(default=None, max_length=1024)
    login_url: str | None = Field(default=None, max_length=1024)
    environment: str | None = Field(default=None, max_length=64)
    status: str = Field(default="active", max_length=32)


class TestProjectCreate(TestProjectBase):
    pass


class TestProjectRead(TestProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
