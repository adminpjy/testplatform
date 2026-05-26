import json
import os
import ssl
from dataclasses import dataclass
from typing import Any
from urllib import request as urlrequest
from urllib.parse import urlparse


@dataclass
class ResolverFallbackResult:
    status: str
    selector: str | None = None
    confidence: float = 0.0
    reason: str = ""


class LLMElementResolver:
    def __init__(self, *, configured: bool | None = None) -> None:
        self.configured = _configured_from_env() if configured is None else configured

    def resolve(self, *, page_context: dict[str, Any], target: str, action: str) -> ResolverFallbackResult:
        if not self.configured:
            return ResolverFallbackResult(status="llm_resolver_not_configured", reason="LLM resolver is disabled.")

        candidates = page_context.get("candidates") or []
        allowed_selectors = {str(candidate.get("selector")) for candidate in candidates if candidate.get("selector")}
        if not allowed_selectors:
            return ResolverFallbackResult(status="llm_no_candidates", reason="No selector candidates were available.")

        try:
            content = _call_llm(
                {
                    "task": "choose_element_selector",
                    "instruction": "Choose exactly one selector from candidates, or null if none is safe.",
                    "target": target,
                    "action": action,
                    "pageContext": {
                        "url": page_context.get("url"),
                        "title": page_context.get("title"),
                        "visibleText": str(page_context.get("visible_text") or "")[:1800],
                        "candidates": candidates[:8],
                    },
                    "responseSchema": {"selector": None, "confidence": 0.0, "reason": ""},
                }
            )
            parsed = _extract_json_object(content)
            selector = parsed.get("selector")
            if selector and str(selector) in allowed_selectors:
                return ResolverFallbackResult(
                    status="llm_selected_candidate",
                    selector=str(selector),
                    confidence=float(parsed.get("confidence") or 0.72),
                    reason=str(parsed.get("reason") or "LLM selected a candidate."),
                )
            return ResolverFallbackResult(status="llm_no_candidate", reason=str(parsed.get("reason") or "LLM did not select a safe selector."))
        except Exception as exc:
            return ResolverFallbackResult(status="llm_error", reason=str(exc))


def _configured_from_env() -> bool:
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    return provider in {"openai", "openai-compatible", "openai_compatible"} and bool(os.getenv("TEST_LLM_BASE_URL")) and bool(os.getenv("TEST_LLM_API_KEY"))


def _call_llm(payload: dict[str, Any]) -> str:
    api_key = os.getenv("TEST_LLM_API_KEY", "")
    body = {
        "model": os.getenv("TEST_LLM_MODEL", "DeepSeek-V4"),
        "messages": [
            {
                "role": "system",
                "content": "You resolve browser element candidates for functional testing. Return strict JSON only.",
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0,
        "stream": False,
        "max_tokens": 512,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(
        _completion_url(os.getenv("TEST_LLM_BASE_URL", "")),
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    context = None
    if os.getenv("TEST_LLM_VERIFY_SSL", "true").strip().lower() in {"0", "false", "no"}:
        context = ssl._create_unverified_context()
    with urlrequest.urlopen(req, timeout=_int_env("TEST_LLM_TIMEOUT_SECONDS", 120), context=context) as response:
        response_body = json.loads(response.read().decode("utf-8"))
    return str(response_body["choices"][0]["message"]["content"])


def _completion_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    parsed = urlparse(base)
    if parsed.path.rstrip("/").endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/chat/completions"


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("LLM resolver did not return a JSON object.")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
