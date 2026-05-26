import os
import time
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


@dataclass
class PageReadyState:
    ready: bool
    reason: str
    waited_ms: int
    url: str | None = None
    title: str | None = None
    ready_state: str | None = None
    text_length: int = 0
    control_count: int = 0
    loading_visible: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "reason": self.reason,
            "waited_ms": self.waited_ms,
            "url": self.url,
            "title": self.title,
            "ready_state": self.ready_state,
            "text_length": self.text_length,
            "control_count": self.control_count,
            "loading_visible": self.loading_visible,
        }


def wait_for_page_ready(
    page: Any,
    *,
    timeout_ms: int | None = None,
    settle_ms: int | None = None,
) -> PageReadyState:
    timeout_ms = timeout_ms or _int_env("PAGE_READY_TIMEOUT_MS", _int_env("GOAL_PAGE_READY_TIMEOUT_MS", 12_000))
    settle_ms = settle_ms if settle_ms is not None else _int_env("PAGE_READY_SETTLE_MS", 500)
    started = time.monotonic()
    deadline = started + max(timeout_ms, 1) / 1000
    last_state = PageReadyState(False, "not_checked", 0)

    _safe_load_state(page, "domcontentloaded", min(timeout_ms, 5_000))
    last_state = _inspect_page(page, started)
    if _is_ready(last_state):
        if settle_ms > 0:
            try:
                page.wait_for_timeout(settle_ms)
            except PlaywrightError:
                pass
        refreshed = _inspect_page(page, started)
        if _is_ready(refreshed):
            refreshed.ready = True
            refreshed.reason = "page_ready"
            return refreshed

    if _bool_env("PLAYWRIGHT_WAIT_NETWORK_IDLE", True):
        _safe_load_state(page, "networkidle", _int_env("PLAYWRIGHT_NETWORK_IDLE_TIMEOUT_MS", 2_500))

    while time.monotonic() < deadline:
        last_state = _inspect_page(page, started)
        if _is_ready(last_state):
            if settle_ms > 0:
                try:
                    page.wait_for_timeout(settle_ms)
                except PlaywrightError:
                    pass
            refreshed = _inspect_page(page, started)
            if _is_ready(refreshed):
                refreshed.ready = True
                refreshed.reason = "page_ready"
                return refreshed
            last_state = refreshed
        try:
            page.wait_for_timeout(250)
        except PlaywrightError:
            break

    last_state.ready = False
    last_state.reason = "page_ready_timeout"
    return last_state


def _safe_load_state(page: Any, state: str, timeout_ms: int) -> None:
    try:
        page.wait_for_load_state(state, timeout=max(timeout_ms, 1))
    except (PlaywrightError, PlaywrightTimeoutError):
        return


def _inspect_page(page: Any, started: float) -> PageReadyState:
    try:
        payload = page.evaluate(
            """() => {
                const body = document.body;
                const text = body ? (body.innerText || "").trim() : "";
                const controls = document.querySelectorAll([
                  "input",
                  "textarea",
                  "select",
                  "button",
                  "a[href]",
                  "table",
                  "[role='button']",
                  "[role='menuitem']",
                  "[role='row']",
                  "[contenteditable='true']"
                ].join(",")).length;
                const loadingSelectors = [
                  ".ant-spin-spinning",
                  ".ant-spin",
                  ".el-loading-mask",
                  ".el-loading-spinner",
                  ".loading",
                  ".spinner",
                  "[aria-busy='true']",
                  "[data-loading='true']"
                ];
                const loadingVisible = loadingSelectors.some((selector) =>
                  Array.from(document.querySelectorAll(selector)).some((element) => {
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== "none"
                      && style.visibility !== "hidden"
                      && Number(style.opacity || "1") > 0
                      && rect.width > 0
                      && rect.height > 0;
                  })
                );
                return {
                  url: location.href,
                  title: document.title || "",
                  readyState: document.readyState,
                  textLength: text.length,
                  controlCount: controls,
                  loadingVisible
                };
            }"""
        )
        return PageReadyState(
            ready=False,
            reason="waiting",
            waited_ms=_elapsed_ms(started),
            url=str(payload.get("url") or ""),
            title=str(payload.get("title") or ""),
            ready_state=str(payload.get("readyState") or ""),
            text_length=int(payload.get("textLength") or 0),
            control_count=int(payload.get("controlCount") or 0),
            loading_visible=bool(payload.get("loadingVisible")),
        )
    except PlaywrightError as exc:
        return PageReadyState(False, f"inspect_failed:{exc}", _elapsed_ms(started))


def _is_ready(state: PageReadyState) -> bool:
    if state.loading_visible:
        return False
    if state.ready_state not in {"interactive", "complete"}:
        return False
    return state.text_length >= 12 or state.control_count >= 1


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


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
