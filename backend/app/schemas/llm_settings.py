from typing import Any

from pydantic import BaseModel, Field, field_validator


class LLMProfileRead(BaseModel):
    id: str
    name: str
    provider: str = "openai_compatible"
    baseUrl: str
    model: str
    stream: bool = False
    verifySsl: bool = True
    timeoutSeconds: int = 120
    maxTokens: int = 8192
    temperature: float = 0.0
    topP: float = 1.0
    caBundle: str = ""
    trustEnv: bool = True
    hasApiKey: bool = False
    apiKeyMasked: str | None = None


class LLMSettingsRead(BaseModel):
    activeProfileId: str
    profiles: list[LLMProfileRead] = Field(default_factory=list)
    effective: LLMProfileRead | None = None


class LLMProfileUpdate(BaseModel):
    id: str
    name: str
    provider: str = "openai_compatible"
    baseUrl: str
    apiKey: str | None = None
    model: str = "DeepSeek-V4"
    stream: bool = False
    verifySsl: bool = True
    timeoutSeconds: int = 120
    maxTokens: int = 8192
    temperature: float = 0.0
    topP: float = 1.0
    caBundle: str = ""
    trustEnv: bool = True

    @field_validator("id", "name", "baseUrl", "model")
    @classmethod
    def require_text(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("字段不能为空")
        return text


class LLMSettingsUpdate(BaseModel):
    activeProfileId: str
    profiles: list[LLMProfileUpdate]

    @field_validator("profiles")
    @classmethod
    def require_profiles(cls, value: list[LLMProfileUpdate]) -> list[LLMProfileUpdate]:
        if not value:
            raise ValueError("至少保留一个 LLM 服务配置")
        ids = [item.id for item in value]
        if len(set(ids)) != len(ids):
            raise ValueError("LLM 服务 ID 不能重复")
        return value


class LLMRuntimeConfig(BaseModel):
    profile_id: str
    profile_name: str
    provider: str
    base_url: str
    api_key: str
    model: str
    stream: bool
    timeout_seconds: int
    max_tokens: int
    temperature: float
    top_p: float
    verify_ssl: bool
    ca_bundle: str = ""
    trust_env: bool = True

    def public_metadata(self) -> dict[str, Any]:
        return {
            "profileId": self.profile_id,
            "profileName": self.profile_name,
            "provider": self.provider,
            "model": self.model,
            "endpoint": self.base_url,
            "stream": self.stream,
            "trustEnv": self.trust_env,
        }
