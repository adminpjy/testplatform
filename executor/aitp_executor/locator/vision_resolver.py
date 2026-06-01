import base64
import json
import os
import re
import ssl
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from executor.aitp_executor.runner.page_waiter import wait_for_page_ready

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency guard for stripped executor images
    httpx = None  # type: ignore[assignment]


@dataclass
class VisionResult:
    status: str
    selector: str | None = None
    point: dict[str, float] | None = None
    confidence: float = 0.0
    reason: str = ""
    overlay_screenshot_path: str | None = None


class VisionResolver:
    def __init__(
        self,
        *,
        configured: bool | None = None,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.endpoint = _clean_text(endpoint or os.getenv("VISION_MODEL_ENDPOINT") or os.getenv("TEST_LLM_BASE_URL"))
        self.api_key = _clean_text(api_key or os.getenv("VISION_MODEL_API_KEY") or os.getenv("TEST_LLM_API_KEY"))
        self.model = _clean_text(model or os.getenv("VISION_MODEL_NAME") or os.getenv("TEST_LLM_MODEL") or "DeepSeek-V4")
        self.timeout_seconds = timeout_seconds or _int_env("VISION_MODEL_TIMEOUT", _int_env("TEST_LLM_TIMEOUT_SECONDS", 60))
        self.verify_ssl = _bool_env("VISION_MODEL_VERIFY_SSL", _bool_env("TEST_LLM_VERIFY_SSL", True))
        self.ca_bundle = _clean_text(os.getenv("VISION_MODEL_CA_BUNDLE") or os.getenv("TEST_LLM_CA_BUNDLE"))
        self.trust_env = _bool_env("VISION_MODEL_TRUST_ENV", _bool_env("TEST_LLM_TRUST_ENV", True))
        self.configured = (
            configured
            if configured is not None
            else _bool_env("VISION_FALLBACK_ENABLED", bool(self.endpoint and self.api_key and self.model))
        )

    def resolve(self, *, page: Any, target: str, action: str) -> VisionResult:
        overlay_path = self._write_overlay_screenshot(page, target=target, action=action)
        if not self.configured or not self.endpoint or not self.api_key or not self.model:
            return VisionResult(
                status="vision_fallback_not_configured",
                reason="视觉兜底未配置完整：需要启用 VISION_FALLBACK_ENABLED，并提供模型 endpoint、api_key 和 model。",
                overlay_screenshot_path=overlay_path,
            )
        if httpx is None:
            return VisionResult(
                status="vision_provider_unavailable",
                reason="视觉兜底需要 httpx 运行时依赖，但当前执行环境未安装。",
                overlay_screenshot_path=overlay_path,
            )
        if not overlay_path:
            return VisionResult(
                status="vision_screenshot_failed",
                reason="页面截图失败，无法执行视觉兜底。",
                overlay_screenshot_path=overlay_path,
            )
        try:
            response_text = self._complete_with_image(Path(overlay_path), target=target, action=action)
            candidate = _parse_json_object(response_text)
            point = _point_from_candidate(candidate)
            confidence = _float_value(candidate.get("confidence"), 0.0)
            if point is not None and confidence >= 0.2:
                return VisionResult(
                    status="vision_point",
                    point=point,
                    confidence=confidence,
                    reason=str(candidate.get("reason") or "vision model returned click point"),
                    overlay_screenshot_path=overlay_path,
                )
            return VisionResult(
                status="vision_no_candidate",
                confidence=confidence,
                reason=str(candidate.get("reason") or "视觉模型未返回可点击坐标。"),
                overlay_screenshot_path=overlay_path,
            )
        except Exception as exc:
            return VisionResult(
                status="vision_request_failed",
                reason=_request_error_summary(exc),
                overlay_screenshot_path=overlay_path,
            )

    def _complete_with_image(self, screenshot_path: Path, *, target: str, action: str) -> str:
        if httpx is None:  # pragma: no cover
            raise RuntimeError("httpx is not installed")
        image_bytes = screenshot_path.read_bytes()
        image_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是企业信息系统测试执行器的视觉定位模块。只返回 JSON，不要输出解释文字。",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "请在截图中寻找需要操作的页面元素，并返回视口坐标。"
                                f"操作 action={action}，目标 target={target}。"
                                "只返回 JSON：{\"x\":数字,\"y\":数字,\"confidence\":0到1,\"reason\":\"简短原因\"}。"
                                "如果没有可靠目标，返回 {\"x\":null,\"y\":null,\"confidence\":0,\"reason\":\"未找到\"}。"
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
            "temperature": 0,
            "stream": False,
            "max_tokens": 512,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=float(self.timeout_seconds), verify=self._verify_value(), trust_env=self.trust_env) as client:
            response = client.post(self._completion_url(), json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        return str((body.get("choices") or [{}])[0].get("message", {}).get("content") or "")

    def _completion_url(self) -> str:
        if self.endpoint.endswith("/chat/completions"):
            return self.endpoint
        parsed = urlparse(self.endpoint)
        if parsed.path.rstrip("/").endswith("/v1"):
            return f"{self.endpoint.rstrip('/')}/chat/completions"
        return f"{self.endpoint.rstrip('/')}/chat/completions"

    def _verify_value(self) -> bool | str | ssl.SSLContext:
        if not self.verify_ssl:
            return False
        if self.ca_bundle:
            bundle = Path(self.ca_bundle)
            if bundle.exists():
                return str(bundle)
        context = _system_trust_context()
        if context is not None:
            return context
        return True

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


def _clean_text(value: str | None) -> str:
    text = str(value or "").strip()
    return text.strip("\"'`“”‘’").strip()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(float(str(os.getenv(name) or default)))
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


def _point_from_candidate(candidate: dict[str, Any]) -> dict[str, float] | None:
    x = candidate.get("x")
    y = candidate.get("y")
    if x is None or y is None:
        point = candidate.get("point") if isinstance(candidate.get("point"), dict) else {}
        x = point.get("x")
        y = point.get("y")
    try:
        x_value = float(x)
        y_value = float(y)
    except (TypeError, ValueError):
        return None
    if x_value < 0 or y_value < 0:
        return None
    return {"x": x_value, "y": y_value}


def _system_trust_context() -> ssl.SSLContext | None:
    try:
        import truststore
    except Exception:
        return None
    try:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return None


def _request_error_summary(exc: BaseException) -> str:
    text = re.sub(r"\s+", " ", str(exc)).strip()
    if not text:
        text = exc.__class__.__name__
    return f"视觉模型请求失败：{text[:500]}"
