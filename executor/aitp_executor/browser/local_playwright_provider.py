from playwright.sync_api import sync_playwright

from executor.aitp_executor.browser.sandbox_provider import BrowserSession


class LocalPlaywrightProvider:
    def __init__(self, *, headless: bool = True, viewport: dict | None = None) -> None:
        self.headless = headless
        self.viewport = viewport or {"width": 1440, "height": 960}

    def start(self) -> BrowserSession:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=self.headless)
        context = browser.new_context(viewport=self.viewport)
        page = context.new_page()
        page.set_default_timeout(10_000)
        return BrowserSession(playwright=playwright, browser=browser, context=context, page=page)
