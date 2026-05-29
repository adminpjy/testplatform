from executor.aitp_executor.browser.local_playwright_provider import LocalPlaywrightProvider


class CubeSandboxProvider(LocalPlaywrightProvider):
    """First-stage adapter placeholder.

    When LOCAL_BROWSER is enabled, this provider uses local Playwright while
    keeping the same provider boundary for later remote sandbox integration.
    """

    def __init__(self, *, headless: bool = True, viewport: dict | None = None) -> None:
        super().__init__(
            headless=headless,
            viewport=viewport,
            ignore_https_errors=True,
            auto_continue_security_interstitial=True,
        )
