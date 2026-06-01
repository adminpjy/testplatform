from pathlib import Path
import ssl
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.openai_compatible import OpenAICompatibleProvider
from app.llm.provider import LLMProviderError, LLMRequest


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


def test_completion_url_accepts_pasted_full_endpoint() -> None:
    provider = OpenAICompatibleProvider(
        base_url="  “https://example.test/v1/chat/completions/”  ",
        api_key="test-key",
        model="DeepSeek-V4",
    )

    assert provider._completion_url() == "https://example.test/v1/chat/completions"


def test_http_client_respects_trust_env_setting(monkeypatch) -> None:
    captured_kwargs: dict = {}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            captured_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, json: dict, headers: dict):
            return _JsonResponse({"choices": [{"message": {"content": "{\"ok\":true}"}}]})

    monkeypatch.setattr("app.llm.openai_compatible.httpx.Client", FakeClient)

    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="DeepSeek-V4",
        trust_env=False,
    )
    result = provider.complete(LLMRequest(system_prompt="s", user_prompt="u", stream=False))

    assert result == "{\"ok\":true}"
    assert captured_kwargs["trust_env"] is False


def test_connect_error_includes_certificate_hint(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, json: dict, headers: dict):
            request = httpx.Request("POST", url)
            cert_error = ssl.SSLCertVerificationError("certificate verify failed")
            raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed", request=request) from cert_error

    monkeypatch.setattr("app.llm.openai_compatible.httpx.Client", FakeClient)

    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="DeepSeek-V4",
    )

    with pytest.raises(LLMProviderError) as exc_info:
        provider.complete(LLMRequest(system_prompt="s", user_prompt="u", stream=False))

    message = str(exc_info.value)
    assert "ConnectError" in message
    assert "certificate verify failed" in message
    assert "CA Bundle" in message


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
