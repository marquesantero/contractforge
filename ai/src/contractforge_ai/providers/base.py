"""Base types for model providers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

ProviderName = Literal["offline", "openai", "azure_openai", "databricks", "deepseek", "anthropic", "gemini", "bedrock"]


class ProviderConfigurationError(RuntimeError):
    """Raised when provider configuration is incomplete or invalid."""


class ProviderExecutionError(RuntimeError):
    """Raised when a provider call fails."""


@dataclass(frozen=True)
class GenerationOptions:
    """Model generation controls shared by providers."""

    temperature: float | None = None
    max_output_tokens: int | None = None
    response_schema: dict[str, Any] | None = None
    response_schema_name: str | None = None
    response_schema_strict: bool = True


@dataclass(frozen=True)
class ProviderConfig:
    """Provider configuration loaded from explicit arguments or environment variables."""

    provider: ProviderName = "offline"
    model: str | None = None
    api_key: str | None = None
    endpoint: str | None = None
    api_version: str | None = None
    organization: str | None = None
    project: str | None = None
    timeout: float | None = None
    max_retries: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("model", "api_key", "endpoint", "api_version", "organization", "project"):
            value = getattr(self, field_name)
            if isinstance(value, str):
                object.__setattr__(self, field_name, value.strip())

    @classmethod
    def from_env(cls, provider: str | None = None) -> "ProviderConfig":
        from contractforge_ai.providers.env import provider_config_from_env

        return provider_config_from_env(cls, provider)

    def to_safe_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data.get("api_key"):
            data["api_key"] = "[REDACTED]"
        return data


class ModelProvider(Protocol):
    """Interface implemented by model providers."""

    name: str

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        options: GenerationOptions | None = None,
    ) -> str:
        """Return a completion for the supplied prompt."""

