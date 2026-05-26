from dataclasses import dataclass
from collections.abc import Iterator
from typing import Protocol

from app.core.config import Settings, settings


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    user_prompt: str
    stream: bool = True
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None


class LLMProvider(Protocol):
    def complete(self, request: LLMRequest) -> str:
        pass

    def stream_complete(self, request: LLMRequest) -> Iterator[str]:
        pass


def get_llm_provider(config: Settings = settings) -> LLMProvider:
    provider_name = config.llm_provider.strip().lower()
    if provider_name == "mock":
        from app.llm.mock_provider import MockLLMProvider

        return MockLLMProvider()
    if provider_name in {"openai", "openai-compatible", "openai_compatible"}:
        from app.llm.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(
            base_url=config.test_llm_base_url,
            api_key=config.test_llm_api_key.get_secret_value() if config.test_llm_api_key else "",
            model=config.test_llm_model,
            timeout_seconds=config.test_llm_timeout_seconds,
            max_tokens=config.test_llm_max_tokens,
            temperature=config.test_llm_temperature,
            top_p=config.test_llm_top_p,
            verify_ssl=config.test_llm_verify_ssl,
            ca_bundle=config.test_llm_ca_bundle,
        )
    raise LLMProviderError(f"Unsupported LLM provider: {provider_name}")
