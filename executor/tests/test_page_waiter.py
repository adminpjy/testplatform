from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class EmptyEvaluatePage:
    def wait_for_load_state(self, _state: str, *, timeout: int) -> None:
        return None

    def evaluate(self, _script: str) -> None:
        return None

    def wait_for_timeout(self, _timeout: int) -> None:
        return None


def test_wait_for_page_ready_handles_empty_evaluate_payload() -> None:
    state = wait_for_page_ready(EmptyEvaluatePage(), timeout_ms=1, settle_ms=0)

    assert state.ready is False
    assert state.reason == "page_ready_timeout"
