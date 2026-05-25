from typing import Callable, TypeVar

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

T = TypeVar("T")


class RecoveryPolicy:
    def retry_once(self, operation: Callable[[], T]) -> T:
        try:
            return operation()
        except PlaywrightTimeoutError:
            return operation()
