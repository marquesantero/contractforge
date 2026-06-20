"""Model provider abstractions."""

from contractforge_ai.providers.anthropic import AnthropicProvider
from contractforge_ai.providers.bedrock import BedrockProvider
from contractforge_ai.providers.base import (
    GenerationOptions,
    ModelProvider,
    ProviderConfig,
    ProviderConfigurationError,
    ProviderExecutionError,
)
from contractforge_ai.providers.capabilities import (
    DatabricksDependencyMode,
    ProviderCapabilityError,
    ProviderCapabilities,
    ProviderPriority,
    ProviderStatus,
    StructuredOutputStrategy,
    TransportMode,
    get_provider_capabilities,
    implemented_provider_names,
    list_provider_capabilities,
    planned_provider_names,
)
from contractforge_ai.providers.databricks import DatabricksModelServingProvider
from contractforge_ai.providers.deepseek import DeepSeekProvider
from contractforge_ai.providers.factory import create_provider, registered_provider_names
from contractforge_ai.providers.gemini import GeminiProvider
from contractforge_ai.providers.offline import OfflineProvider
from contractforge_ai.providers.openai import AzureOpenAIProvider, OpenAIProvider
from contractforge_ai.providers.routing import (
    ProviderRouteRecommendation,
    ProviderRoutingReport,
    ProviderRoutingRequest,
    ProviderTask,
    recommend_providers,
)

__all__ = [
    "AnthropicProvider",
    "AzureOpenAIProvider",
    "BedrockProvider",
    "DatabricksDependencyMode",
    "DatabricksModelServingProvider",
    "DeepSeekProvider",
    "GenerationOptions",
    "GeminiProvider",
    "ModelProvider",
    "OfflineProvider",
    "OpenAIProvider",
    "ProviderCapabilityError",
    "ProviderCapabilities",
    "ProviderConfig",
    "ProviderConfigurationError",
    "ProviderPriority",
    "ProviderRouteRecommendation",
    "ProviderRoutingReport",
    "ProviderRoutingRequest",
    "ProviderExecutionError",
    "ProviderStatus",
    "ProviderTask",
    "StructuredOutputStrategy",
    "TransportMode",
    "create_provider",
    "get_provider_capabilities",
    "implemented_provider_names",
    "list_provider_capabilities",
    "planned_provider_names",
    "recommend_providers",
    "registered_provider_names",
]
