from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

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
    runs_root: str = Field(default="artifacts/runs", alias="RUNS_ROOT")
    workspaces_root: str = Field(default="data/ai-test/workspaces", alias="WORKSPACES_ROOT")
    executor_path: str = Field(default="executor/run_case.py", alias="EXECUTOR_PATH")
    executor_mode: str = Field(default="local", alias="EXECUTOR_MODE")
    max_concurrent_runs: int = Field(default=2, alias="MAX_CONCURRENT_RUNS")
    run_timeout_seconds: int = Field(default=600, alias="RUN_TIMEOUT_SECONDS")
    allowed_base_url_prefixes: str = Field(default="", alias="ALLOWED_BASE_URL_PREFIXES")
    local_secret_key: SecretStr = Field(default=SecretStr("local-development-secret"), alias="LOCAL_SECRET_KEY")
    llm_provider: str = Field(default="openai_compatible", alias="LLM_PROVIDER")
    test_llm_base_url: str = Field(default="", alias="TEST_LLM_BASE_URL")
    test_llm_api_key: SecretStr | None = Field(default=None, alias="TEST_LLM_API_KEY")
    test_llm_model: str = Field(default="DeepSeek-V4", alias="TEST_LLM_MODEL")
    test_llm_stream: bool = Field(default=True, alias="TEST_LLM_STREAM")
    test_llm_timeout_seconds: int = Field(default=120, alias="TEST_LLM_TIMEOUT_SECONDS")
    test_llm_max_tokens: int = Field(default=8192, alias="TEST_LLM_MAX_TOKENS")
    test_llm_temperature: float = Field(default=0.0, alias="TEST_LLM_TEMPERATURE")
    test_llm_top_p: float = Field(default=1.0, alias="TEST_LLM_TOP_P")
    test_llm_verify_ssl: bool = Field(default=True, alias="TEST_LLM_VERIFY_SSL")
    test_llm_ca_bundle: str = Field(default="", alias="TEST_LLM_CA_BUNDLE")
    cube_api_url: str = Field(default="", alias="CUBE_API_URL")
    cube_api_key: SecretStr | None = Field(default=None, alias="CUBE_API_KEY")
    cube_browser_template_id: str = Field(default="", alias="CUBE_BROWSER_TEMPLATE_ID")
    cube_template_id: str = Field(default="", alias="CUBE_TEMPLATE_ID")
    cube_cdp_port: int = Field(default=9000, alias="CUBE_CDP_PORT")
    cube_sandbox_timeout_seconds: int = Field(default=900, alias="CUBE_SANDBOX_TIMEOUT_SECONDS")
    cube_sandbox_ttl_seconds: int = Field(default=900, alias="CUBE_SANDBOX_TTL_SECONDS")
    keep_sandbox_on_failure: bool = Field(default=True, alias="KEEP_SANDBOX_ON_FAILURE")
    local_browser: bool = Field(default=True, alias="LOCAL_BROWSER")
    vision_fallback_enabled: bool = Field(default=False, alias="VISION_FALLBACK_ENABLED")
    vision_model_provider: str = Field(default="", alias="VISION_MODEL_PROVIDER")
    vision_model_endpoint: str = Field(default="", alias="VISION_MODEL_ENDPOINT")
    vision_model_api_key: SecretStr | None = Field(default=None, alias="VISION_MODEL_API_KEY")
    vision_model_timeout: int = Field(default=30, alias="VISION_MODEL_TIMEOUT")
    playwright_ignore_https_errors: bool = Field(default=False, alias="PLAYWRIGHT_IGNORE_HTTPS_ERRORS")
    playwright_auto_continue_security_interstitial: bool = Field(
        default=False,
        alias="PLAYWRIGHT_AUTO_CONTINUE_SECURITY_INTERSTITIAL",
    )
    playwright_proxy_server: str = Field(default="", alias="PLAYWRIGHT_PROXY_SERVER")
    playwright_proxy_bypass: str = Field(default="", alias="PLAYWRIGHT_PROXY_BYPASS")
    playwright_proxy_username: str = Field(default="", alias="PLAYWRIGHT_PROXY_USERNAME")
    playwright_proxy_password: SecretStr | None = Field(default=None, alias="PLAYWRIGHT_PROXY_PASSWORD")
    playwright_user_agent: str = Field(default="", alias="PLAYWRIGHT_USER_AGENT")
    playwright_client_cert_origin: str = Field(default="", alias="PLAYWRIGHT_CLIENT_CERT_ORIGIN")
    playwright_client_cert_path: str = Field(default="", alias="PLAYWRIGHT_CLIENT_CERT_PATH")
    playwright_client_key_path: str = Field(default="", alias="PLAYWRIGHT_CLIENT_KEY_PATH")
    playwright_client_cert_pfx_path: str = Field(default="", alias="PLAYWRIGHT_CLIENT_CERT_PFX_PATH")
    playwright_client_cert_passphrase: SecretStr | None = Field(default=None, alias="PLAYWRIGHT_CLIENT_CERT_PASSPHRASE")
    real_mis_base_url: str = Field(default="", alias="REAL_MIS_BASE_URL")
    real_mis_login_url: str = Field(default="", alias="REAL_MIS_LOGIN_URL")
    real_mis_username: str = Field(default="", alias="REAL_MIS_USERNAME")
    real_mis_password: SecretStr | None = Field(default=None, alias="REAL_MIS_PASSWORD")
    goal_max_iterations: int = Field(default=12, alias="GOAL_MAX_ITERATIONS")
    goal_total_timeout_ms: int = Field(default=90000, alias="GOAL_TOTAL_TIMEOUT_MS")
    goal_single_action_timeout_ms: int = Field(default=15000, alias="GOAL_SINGLE_ACTION_TIMEOUT_MS")
    trace_viewer_enabled: bool = Field(default=True, alias="TRACE_VIEWER_ENABLED")
    trace_viewer_host: str = Field(default="0.0.0.0", alias="TRACE_VIEWER_HOST")
    trace_viewer_public_host: str = Field(default="localhost", alias="TRACE_VIEWER_PUBLIC_HOST")
    trace_viewer_port_start: int = Field(default=39000, alias="TRACE_VIEWER_PORT_START")
    trace_viewer_port_end: int = Field(default=39100, alias="TRACE_VIEWER_PORT_END")
    trace_viewer_idle_timeout_seconds: int = Field(default=600, alias="TRACE_VIEWER_IDLE_TIMEOUT_SECONDS")

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

    @property
    def allowed_base_url_prefix_list(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.allowed_base_url_prefixes.split(",") if item.strip()]

    def is_allowed_url(self, value: str | None) -> bool:
        if not value:
            return True
        prefixes = self.allowed_base_url_prefix_list
        if not prefixes:
            return True
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            return False
        normalized = value.rstrip("/")
        return any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in prefixes)

    def ensure_runtime_dirs(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.artifacts_dir).mkdir(parents=True, exist_ok=True)
        Path(self.reports_dir).mkdir(parents=True, exist_ok=True)
        Path(self.runs_root).mkdir(parents=True, exist_ok=True)
        Path(self.workspaces_root).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
