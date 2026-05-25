from dataclasses import dataclass
from typing import Any


@dataclass
class VisionResult:
    status: str
    selector: str | None = None
    confidence: float = 0.0
    reason: str = ""


class VisionResolver:
    def __init__(self, *, configured: bool = False) -> None:
        self.configured = configured

    def resolve(self, *, page: Any, target: str, action: str) -> VisionResult:
        if not self.configured:
            return VisionResult(
                status="vision_fallback_not_configured",
                reason="Vision fallback is not configured for local stage 6 execution.",
            )
        return VisionResult(status="vision_no_candidate", reason="Vision resolver did not return a candidate.")
