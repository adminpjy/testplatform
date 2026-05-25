from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings, settings


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    user_prompt: str
    stream: bool = True
    temperature: float = 0.0


class LLMProvider(Protocol):
    def complete(self, request: LLMRequest) -> str:
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
        )
    raise LLMProviderError(f"Unsupported LLM provider: {provider_name}")
