from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_name: str = "Enterprise MIS Intelligent Functional Testing Platform"
    app_version: str = "0.1.0"
    app_environment: str = "development"
    database_url: str = Field(default="sqlite:///./data/aitp.db", alias="DATABASE_URL")
    backend_host: str = Field(default="127.0.0.1", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    data_dir: str = Field(default="data", alias="DATA_DIR")
    artifacts_dir: str = Field(default="artifacts", alias="ARTIFACTS_DIR")
    reports_dir: str = Field(default="reports", alias="REPORTS_DIR")
    local_secret_key: SecretStr = Field(default=SecretStr("local-development-secret"), alias="LOCAL_SECRET_KEY")
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    test_llm_base_url: str = Field(default="", alias="TEST_LLM_BASE_URL")
    test_llm_api_key: SecretStr | None = Field(default=None, alias="TEST_LLM_API_KEY")
    test_llm_model: str = Field(default="DeepSeek-V4", alias="TEST_LLM_MODEL")
    test_llm_stream: bool = Field(default=True, alias="TEST_LLM_STREAM")
    vision_fallback_enabled: bool = Field(default=False, alias="VISION_FALLBACK_ENABLED")
    vision_model_provider: str = Field(default="mock", alias="VISION_MODEL_PROVIDER")
    vision_model_endpoint: str = Field(default="", alias="VISION_MODEL_ENDPOINT")
    vision_model_api_key: SecretStr | None = Field(default=None, alias="VISION_MODEL_API_KEY")
    real_mis_base_url: str = Field(default="", alias="REAL_MIS_BASE_URL")
    real_mis_login_url: str = Field(default="", alias="REAL_MIS_LOGIN_URL")
    real_mis_username: str = Field(default="", alias="REAL_MIS_USERNAME")
    real_mis_password: SecretStr | None = Field(default=None, alias="REAL_MIS_PASSWORD")
    goal_max_iterations: int = Field(default=12, alias="GOAL_MAX_ITERATIONS")
    goal_total_timeout_ms: int = Field(default=90000, alias="GOAL_TOTAL_TIMEOUT_MS")
    goal_single_action_timeout_ms: int = Field(default=15000, alias="GOAL_SINGLE_ACTION_TIMEOUT_MS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def safe_database_url(self) -> str:
        url = make_url(self.database_url)
        return url.render_as_string(hide_password=True)

    @property
    def database_dialect(self) -> str:
        return make_url(self.database_url).get_backend_name()

    def ensure_runtime_dirs(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.artifacts_dir).mkdir(parents=True, exist_ok=True)
        Path(self.reports_dir).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
