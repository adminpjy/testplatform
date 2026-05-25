from dataclasses import dataclass
from typing import Any


@dataclass
class ResolverFallbackResult:
    status: str
    selector: str | None = None
    confidence: float = 0.0
    reason: str = ""


class LLMElementResolver:
    def __init__(self, *, configured: bool = False) -> None:
        self.configured = configured

    def resolve(self, *, page_context: dict[str, Any], target: str, action: str) -> ResolverFallbackResult:
        if not self.configured:
            return ResolverFallbackResult(status="llm_resolver_not_configured", reason="LLM resolver is disabled.")
        return ResolverFallbackResult(status="llm_no_candidate", reason="No LLM candidate was returned.")
