"""Provider factory."""

from __future__ import annotations

from typing import Callable

from contractforge_ai.providers.base import ModelProvider, ProviderConfig, ProviderConfigurationError
from contractforge_ai.providers.anthropic import AnthropicProvider
from contractforge_ai.providers.bedrock import BedrockProvider
from contractforge_ai.providers.databricks import DatabricksModelServingProvider
from contractforge_ai.providers.deepseek import DeepSeekProvider
from contractforge_ai.providers.gemini import GeminiProvider
from contractforge_ai.providers.offline import OfflineProvider
from contractforge_ai.providers.openai import AzureOpenAIProvider, OpenAIProvider

ProviderFactory = Callable[[ProviderConfig], ModelProvider]

_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "offline": lambda _config: OfflineProvider(),
    "openai": OpenAIProvider,
    "azure_openai": AzureOpenAIProvider,
    "databricks": DatabricksModelServingProvider,
    "deepseek": DeepSeekProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "bedrock": BedrockProvider,
}


def create_provider(config: ProviderConfig | None = None) -> ModelProvider:
    """Create a provider from configuration."""

    selected = config or ProviderConfig.from_env()
    try:
        factory = _PROVIDER_FACTORIES[selected.provider]
    except KeyError as exc:
        raise ProviderConfigurationError(f"Unsupported provider: {selected.provider}") from exc
    return factory(selected)


def registered_provider_names() -> tuple[str, ...]:
    """Return provider names accepted by the provider factory."""

    return tuple(_PROVIDER_FACTORIES)
