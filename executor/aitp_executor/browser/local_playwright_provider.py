import os

from playwright.sync_api import sync_playwright

from executor.aitp_executor.browser.sandbox_provider import BrowserSession


class LocalPlaywrightProvider:
    def __init__(
        self,
        *,
        headless: bool = True,
        viewport: dict | None = None,
        ignore_https_errors: bool | None = None,
        auto_continue_security_interstitial: bool | None = None,
    ) -> None:
        self.headless = headless
        self.viewport = viewport or {"width": 1440, "height": 960}
        self.ignore_https_errors = ignore_https_errors
        self.auto_continue_security_interstitial = auto_continue_security_interstitial

    def start(self) -> BrowserSession:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=self.headless,
            **_launch_options(
                ignore_https_errors=self.ignore_https_errors,
                auto_continue_security_interstitial=self.auto_continue_security_interstitial,
            ),
        )
        context = browser.new_context(
            viewport=self.viewport,
            **_context_options(
                ignore_https_errors=self.ignore_https_errors,
                auto_continue_security_interstitial=self.auto_continue_security_interstitial,
            ),
        )
        page = context.new_page()
        page.set_default_timeout(_int_env("GOAL_SINGLE_ACTION_TIMEOUT_MS", 15_000))
        return BrowserSession(playwright=playwright, browser=browser, context=context, page=page)


def _launch_options(
    *,
    ignore_https_errors: bool | None = None,
    auto_continue_security_interstitial: bool | None = None,
) -> dict:
    options: dict = {}
    args: list[str] = []
    if _certificate_bypass_enabled(
        ignore_https_errors=ignore_https_errors,
        auto_continue_security_interstitial=auto_continue_security_interstitial,
    ):
        args.extend(
            [
                "--ignore-certificate-errors",
                "--allow-insecure-localhost",
                "--allow-running-insecure-content",
            ]
        )
    if args:
        options["args"] = args
    proxy = _proxy_options()
    if proxy:
        options["proxy"] = proxy
    return options


def _context_options(
    *,
    ignore_https_errors: bool | None = None,
    auto_continue_security_interstitial: bool | None = None,
) -> dict:
    options: dict = {
        "ignore_https_errors": _certificate_bypass_enabled(
            ignore_https_errors=ignore_https_errors,
            auto_continue_security_interstitial=auto_continue_security_interstitial,
        ),
    }
    user_agent = os.getenv("PLAYWRIGHT_USER_AGENT", "").strip()
    if user_agent:
        options["user_agent"] = user_agent
    return options


def _certificate_bypass_enabled(
    *,
    ignore_https_errors: bool | None = None,
    auto_continue_security_interstitial: bool | None = None,
) -> bool:
    if ignore_https_errors is not None:
        return bool(ignore_https_errors)
    if auto_continue_security_interstitial is not None and auto_continue_security_interstitial:
        return True
    return _bool_env("PLAYWRIGHT_IGNORE_HTTPS_ERRORS", False) or _bool_env(
        "PLAYWRIGHT_AUTO_CONTINUE_SECURITY_INTERSTITIAL", False
    )


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
