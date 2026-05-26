import os

from playwright.sync_api import sync_playwright

from executor.aitp_executor.browser.sandbox_provider import BrowserSession


class LocalPlaywrightProvider:
    def __init__(self, *, headless: bool = True, viewport: dict | None = None) -> None:
        self.headless = headless
        self.viewport = viewport or {"width": 1440, "height": 960}

    def start(self) -> BrowserSession:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=self.headless, **_launch_options())
        context = browser.new_context(viewport=self.viewport, **_context_options())
        page = context.new_page()
        page.set_default_timeout(_int_env("GOAL_SINGLE_ACTION_TIMEOUT_MS", 15_000))
        return BrowserSession(playwright=playwright, browser=browser, context=context, page=page)


def _launch_options() -> dict:
    options: dict = {}
    proxy = _proxy_options()
    if proxy:
        options["proxy"] = proxy
    return options


def _context_options() -> dict:
    options: dict = {
        "ignore_https_errors": _bool_env("PLAYWRIGHT_IGNORE_HTTPS_ERRORS", False),
    }
    user_agent = os.getenv("PLAYWRIGHT_USER_AGENT", "").strip()
    if user_agent:
        options["user_agent"] = user_agent
    return options


def _proxy_options() -> dict | None:
    server = os.getenv("PLAYWRIGHT_PROXY_SERVER", "").strip()
    if not server:
        return None
    proxy = {"server": server}
    bypass = os.getenv("PLAYWRIGHT_PROXY_BYPASS", "").strip()
    username = os.getenv("PLAYWRIGHT_PROXY_USERNAME", "").strip()
    password = os.getenv("PLAYWRIGHT_PROXY_PASSWORD", "").strip()
    if bypass:
        proxy["bypass"] = bypass
    if username:
        proxy["username"] = username
    if password:
        proxy["password"] = password
    return proxy


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default
