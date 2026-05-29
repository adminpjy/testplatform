from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.openai_compatible import OpenAICompatibleProvider
from app.llm.provider import LLMRequest


def test_complete_falls_back_to_non_stream_when_stream_endpoint_404(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def stream(self, method: str, url: str, json: dict, headers: dict):
            calls.append(("stream", bool(json["stream"])))
            return _FakeStreamContext(_HttpErrorResponse(404))

        def post(self, url: str, json: dict, headers: dict):
            calls.append(("post", bool(json["stream"])))
            return _JsonResponse({"choices": [{"message": {"content": "{\"ok\":true}"}}]})

    monkeypatch.setattr("app.llm.openai_compatible.httpx.Client", FakeClient)

    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1/chat/completions",
        api_key="test-key",
        model="DeepSeek",
    )

    result = provider.complete(LLMRequest(system_prompt="s", user_prompt="u", stream=True))

    assert result == "{\"ok\":true}"
    assert calls == [("stream", True), ("post", False)]


def test_stream_complete_yields_non_stream_response_when_stream_endpoint_404(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def stream(self, method: str, url: str, json: dict, headers: dict):
            calls.append(("stream", bool(json["stream"])))
            return _FakeStreamContext(_HttpErrorResponse(404))

        def post(self, url: str, json: dict, headers: dict):
            calls.append(("post", bool(json["stream"])))
            return _JsonResponse({"choices": [{"message": {"content": "{\"ok\":true}"}}]})

    monkeypatch.setattr("app.llm.openai_compatible.httpx.Client", FakeClient)

    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1/chat/completions",
        api_key="test-key",
        model="DeepSeek",
    )

    chunks = list(provider.stream_complete(LLMRequest(system_prompt="s", user_prompt="u", stream=True)))

    assert chunks == ["{\"ok\":true}"]
    assert calls == [("stream", True), ("post", False)]


class _FakeStreamContext:
    def __init__(self, response) -> None:
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _HttpErrorResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        request = httpx.Request("POST", "https://example.test/v1/chat/completions")
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("stream failed", request=request, response=response)

    def iter_lines(self):
        return iter(())


class _JsonResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload
