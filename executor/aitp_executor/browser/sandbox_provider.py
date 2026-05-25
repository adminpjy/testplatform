from dataclasses import dataclass
from typing import Protocol


@dataclass
class BrowserSession:
    playwright: object
    browser: object
    context: object
    page: object

    def close(self) -> None:
        try:
            self.context.close()
        finally:
            try:
                self.browser.close()
            finally:
                self.playwright.stop()


class SandboxProvider(Protocol):
    def start(self) -> BrowserSession:
        pass
