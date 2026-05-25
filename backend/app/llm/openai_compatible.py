import json

import httpx

from app.llm.provider import LLMProviderError, LLMRequest


class OpenAICompatibleProvider:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

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
            "temperature": request.temperature,
            "stream": request.stream,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        with httpx.Client(timeout=60.0) as client:
            if request.stream:
                return self._complete_streaming(client, url, payload, headers)
            response = client.post(url, json=payload, headers=headers)
            self._raise_for_status(response)
            body = response.json()
            return body["choices"][0]["message"]["content"]

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
