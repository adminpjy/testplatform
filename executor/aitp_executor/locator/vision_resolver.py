from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


@dataclass
class VisionResult:
    status: str
    selector: str | None = None
    confidence: float = 0.0
    reason: str = ""
    overlay_screenshot_path: str | None = None


class VisionResolver:
    def __init__(self, *, configured: bool = False) -> None:
        self.configured = configured

    def resolve(self, *, page: Any, target: str, action: str) -> VisionResult:
        overlay_path = self._write_overlay_screenshot(page, target=target, action=action)
        if not self.configured:
            return VisionResult(
                status="vision_fallback_not_configured",
                reason="Vision fallback is not configured for local stage 6 execution.",
                overlay_screenshot_path=overlay_path,
            )
        return VisionResult(
            status="vision_no_candidate",
            reason="Vision resolver did not return a candidate.",
            overlay_screenshot_path=overlay_path,
        )

    def _write_overlay_screenshot(self, page: Any, *, target: str, action: str) -> str | None:
        try:
            wait_for_page_ready(page)
            safe_target = "".join(char if char.isalnum() else "_" for char in target)[:40] or "target"
            stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            path = Path("artifacts") / "vision-overlays" / f"{stamp}-{action}-{safe_target}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(path), full_page=True)
            return path.as_posix()
        except Exception:
            return None
