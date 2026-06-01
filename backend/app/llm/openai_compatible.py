import json
import re
import ssl
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.llm.provider import LLMProviderError, LLMRequest


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 120,
        max_tokens: int = 8192,
        temperature: float = 0.0,
        top_p: float = 1.0,
        verify_ssl: bool = True,
        ca_bundle: str = "",
        trust_env: bool = True,
    ) -> None:
        self.base_url = _clean_text(base_url).rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.verify_ssl = verify_ssl
        self.ca_bundle = _clean_text(ca_bundle)
        self.trust_env = trust_env

    def complete(self, request: LLMRequest) -> str:
        if not self.base_url:
            raise LLMProviderError("TEST_LLM_BASE_URL is required for the OpenAI-compatible provider.")
        if not self.api_key:
            raise LLMProviderError("TEST_LLM_API_KEY is required for the OpenAI-compatible provider.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = self._completion_url()

        try:
            with httpx.Client(timeout=float(self.timeout_seconds), verify=self._verify_value(), trust_env=self.trust_env) as client:
                if request.stream:
                    try:
                        return self._complete_streaming(client, url, self._payload(request, stream=True), headers)
                    except LLMProviderError as exc:
                        if not _can_retry_without_stream(exc):
                            raise
                return self._complete_non_streaming(client, url, self._payload(request, stream=False), headers)
        except httpx.RequestError as exc:
            raise LLMProviderError(_request_error_message(exc)) from exc

    def stream_complete(self, request: LLMRequest) -> Iterator[str]:
        if not self.base_url:
            raise LLMProviderError("TEST_LLM_BASE_URL is required for the OpenAI-compatible provider.")
        if not self.api_key:
            raise LLMProviderError("TEST_LLM_API_KEY is required for the OpenAI-compatible provider.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=float(self.timeout_seconds), verify=self._verify_value(), trust_env=self.trust_env) as client:
                url = self._completion_url()
                if request.stream:
                    try:
                        yield from self._stream_chunks(client, url, self._payload(request, stream=True), headers)
                        return
                    except LLMProviderError as exc:
                        if not _can_retry_without_stream(exc):
                            raise
                yield self._complete_non_streaming(client, url, self._payload(request, stream=False), headers)
        except httpx.RequestError as exc:
            raise LLMProviderError(_request_error_message(exc)) from exc

    def _payload(self, request: LLMRequest, *, stream: bool) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature if request.temperature is not None else self.temperature,
            "top_p": request.top_p if request.top_p is not None else self.top_p,
            "stream": stream,
        }
        max_tokens = request.max_tokens if request.max_tokens is not None else self.max_tokens
        if max_tokens > 0:
            payload["max_tokens"] = max_tokens
        return payload

    def _completion_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        parsed = urlparse(self.base_url)
        if parsed.path.rstrip("/").endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/chat/completions"

    def _verify_value(self) -> bool | str | ssl.SSLContext:
        if not self.verify_ssl:
            return False
        if self.ca_bundle:
            bundle = Path(self.ca_bundle)
            if not bundle.exists():
                raise LLMProviderError("Configured TEST_LLM_CA_BUNDLE file does not exist.")
            return str(bundle)
        context = _system_trust_context()
        if context is not None:
            return context
        return True

    def _complete_streaming(
        self,
        client: httpx.Client,
        url: str,
        payload: dict,
        headers: dict,
    ) -> str:
        return "".join(self._stream_chunks(client, url, payload, headers))

    def _complete_non_streaming(self, client: httpx.Client, url: str, payload: dict, headers: dict) -> str:
        response = client.post(url, json=payload, headers=headers)
        self._raise_for_status(response)
        body = response.json()
        return body["choices"][0]["message"]["content"]

    def _stream_chunks(
        self,
        client: httpx.Client,
        url: str,
        payload: dict,
        headers: dict,
    ) -> Iterator[str]:
        chunks: list[str] = []
        with client.stream("POST", url, json=payload, headers=headers) as response:
            self._raise_for_status(response)
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                choice = (event.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if content:
                    chunks.append(content)
                    yield content

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"LLM provider request failed with HTTP {exc.response.status_code}.") from exc


def _can_retry_without_stream(exc: LLMProviderError) -> bool:
    text = str(exc)
    return "HTTP 400" in text or "HTTP 404" in text or "HTTP 405" in text


def _clean_text(value: str | None) -> str:
    text = str(value or "").strip()
    return text.strip("\"'`“”‘’").strip()


def _system_trust_context() -> ssl.SSLContext | None:
    try:
        import truststore
    except Exception:
        return None
    try:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return None


def _request_error_message(exc: httpx.RequestError) -> str:
    root_cause = _root_cause_text(exc)
    parts = [f"LLM provider request failed: {exc.__class__.__name__}."]
    if root_cause:
        parts.append(f"底层原因：{root_cause}")
    hint = _request_error_hint(exc, root_cause)
    if hint:
        parts.append(hint)
    return " ".join(parts)


def _root_cause_text(exc: BaseException) -> str:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        next_cause = current.__cause__ or current.__context__
        if next_cause is None:
            break
        current = next_cause
    text = str(current or exc) or str(exc)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500]


def _request_error_hint(exc: httpx.RequestError, root_cause: str) -> str:
    text = root_cause.lower()
    if isinstance(exc, httpx.TimeoutException):
        return "提示：模型服务响应超时，请检查超时秒数、模型排队情况或后端服务器到模型服务的网络。"
    if isinstance(exc, httpx.ConnectError):
        if "certificate_verify_failed" in text or "ssl" in text or "certificate" in text:
            return "提示：这是内网 HTTPS 服务时，curl 可能使用系统证书库，而 Python/httpx 可能不信任企业 CA；请在系统设置中填写 CA Bundle，或在可信内网环境临时关闭 SSL 校验。"
        if "proxy" in text:
            return "提示：请检查后端进程的 HTTP_PROXY/HTTPS_PROXY/NO_PROXY，内网模型地址通常需要加入 NO_PROXY 或关闭读取代理环境变量。"
        if "name or service not known" in text or "temporary failure in name resolution" in text or "nodename" in text:
            return "提示：请检查后端服务器 DNS 是否能解析模型服务域名，注意这是后端进程所在机器的网络。"
        if "connection refused" in text:
            return "提示：模型服务端口拒绝连接，请确认服务地址、端口和防火墙策略。"
        return "提示：请检查后端服务器到模型服务的网络、DNS、代理和证书配置。"
    return ""
