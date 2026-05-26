import json
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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.verify_ssl = verify_ssl
        self.ca_bundle = ca_bundle

    def complete(self, request: LLMRequest) -> str:
        if not self.base_url:
            raise LLMProviderError("TEST_LLM_BASE_URL is required for the OpenAI-compatible provider.")
        if not self.api_key:
            raise LLMProviderError("TEST_LLM_API_KEY is required for the OpenAI-compatible provider.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature if request.temperature is not None else self.temperature,
            "top_p": request.top_p if request.top_p is not None else self.top_p,
            "stream": request.stream,
        }
        max_tokens = request.max_tokens if request.max_tokens is not None else self.max_tokens
        if max_tokens > 0:
            payload["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = self._completion_url()

        with httpx.Client(timeout=float(self.timeout_seconds), verify=self._verify_value()) as client:
            if request.stream:
                return self._complete_streaming(client, url, payload, headers)
            response = client.post(url, json=payload, headers=headers)
            self._raise_for_status(response)
            body = response.json()
            return body["choices"][0]["message"]["content"]

    def _completion_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        parsed = urlparse(self.base_url)
        if parsed.path.rstrip("/").endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/chat/completions"

    def _verify_value(self) -> bool | str:
        if not self.verify_ssl:
            return False
        if self.ca_bundle:
            bundle = Path(self.ca_bundle)
            if not bundle.exists():
                raise LLMProviderError("Configured TEST_LLM_CA_BUNDLE file does not exist.")
            return str(bundle)
        return True

    def _complete_streaming(
        self,
        client: httpx.Client,
        url: str,
        payload: dict,
        headers: dict,
    ) -> str:
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
        return "".join(chunks)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"LLM provider request failed with HTTP {exc.response.status_code}.") from exc
