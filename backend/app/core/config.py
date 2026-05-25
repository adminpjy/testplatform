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
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    test_llm_base_url: str = Field(default="", alias="TEST_LLM_BASE_URL")
    test_llm_api_key: SecretStr | None = Field(default=None, alias="TEST_LLM_API_KEY")
    test_llm_model: str = Field(default="DeepSeek-V4", alias="TEST_LLM_MODEL")
    test_llm_stream: bool = Field(default=True, alias="TEST_LLM_STREAM")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
