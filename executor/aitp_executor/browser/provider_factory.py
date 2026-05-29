import os

from executor.aitp_executor.browser.cube_sandbox_provider import CubeSandboxProvider
from executor.aitp_executor.browser.local_playwright_provider import LocalPlaywrightProvider
from executor.aitp_executor.browser.sandbox_provider import SandboxProvider


def create_sandbox_provider() -> SandboxProvider:
    mode = os.getenv("EXECUTOR_MODE", "local").strip().lower()
    local_browser = _env_bool("LOCAL_BROWSER", True)
    if mode == "cube":
        if local_browser:
            return CubeSandboxProvider(headless=True)
        raise RuntimeError("Cube sandbox provider is configured but remote Cube execution is not implemented in this stage.")
    return LocalPlaywrightProvider(headless=True)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
