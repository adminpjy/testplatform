from executor.aitp_executor.browser.local_playwright_provider import LocalPlaywrightProvider


class CubeSandboxProvider(LocalPlaywrightProvider):
    """First-stage adapter placeholder.

    When CUBE_MOCK or LOCAL_BROWSER is enabled, this provider intentionally uses
    local Playwright while keeping the same provider boundary for later remote
    sandbox integration.
    """

    pass
