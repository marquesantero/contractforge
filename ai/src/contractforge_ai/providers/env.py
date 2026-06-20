"""Environment-based provider configuration loading."""

from __future__ import annotations

import os
from typing import Callable

from contractforge_ai.providers.base import ProviderConfig, ProviderConfigurationError

ProviderConfigLoader = Callable[[type[ProviderConfig]], ProviderConfig]


def provider_config_from_env(cls: type[ProviderConfig], provider: str | None = None) -> ProviderConfig:
    """Load provider configuration from environment variables."""

    selected = (provider or os.getenv("CONTRACTFORGE_AI_PROVIDER") or "offline").strip().lower()
    try:
        loader = _PROVIDER_CONFIG_LOADERS[selected]
    except KeyError as exc:
        raise ProviderConfigurationError(f"Unsupported provider: {selected}") from exc
    return loader(cls)


def _offline_config(cls: type[ProviderConfig]) -> ProviderConfig:
    return cls(provider="offline")


def _openai_config(cls: type[ProviderConfig]) -> ProviderConfig:
    return cls(
        provider="openai",
        model=os.getenv("CONTRACTFORGE_AI_MODEL") or os.getenv("OPENAI_MODEL"),
        api_key=os.getenv("CONTRACTFORGE_AI_API_KEY") or os.getenv("OPENAI_API_KEY"),
        organization=os.getenv("OPENAI_ORG_ID"),
        project=os.getenv("OPENAI_PROJECT"),
        timeout=_float_env("CONTRACTFORGE_AI_TIMEOUT"),
        max_retries=_int_env("CONTRACTFORGE_AI_MAX_RETRIES"),
    )


def _azure_openai_config(cls: type[ProviderConfig]) -> ProviderConfig:
    return cls(
        provider="azure_openai",
        model=(
            os.getenv("CONTRACTFORGE_AI_MODEL")
            or os.getenv("AZURE_OPENAI_DEPLOYMENT")
            or os.getenv("AZURE_OPENAI_MODEL")
        ),
        api_key=os.getenv("CONTRACTFORGE_AI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"),
        endpoint=os.getenv("CONTRACTFORGE_AI_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("CONTRACTFORGE_AI_API_VERSION") or os.getenv("AZURE_OPENAI_API_VERSION"),
        timeout=_float_env("CONTRACTFORGE_AI_TIMEOUT"),
        max_retries=_int_env("CONTRACTFORGE_AI_MAX_RETRIES"),
    )


def _databricks_config(cls: type[ProviderConfig]) -> ProviderConfig:
    return cls(
        provider="databricks",
        model=(
            os.getenv("CONTRACTFORGE_AI_MODEL")
            or os.getenv("DATABRICKS_SERVING_ENDPOINT")
            or os.getenv("DATABRICKS_MODEL_SERVING_ENDPOINT")
        ),
        api_key=os.getenv("CONTRACTFORGE_AI_API_KEY") or os.getenv("DATABRICKS_TOKEN"),
        endpoint=os.getenv("CONTRACTFORGE_AI_ENDPOINT") or os.getenv("DATABRICKS_HOST"),
        timeout=_float_env("CONTRACTFORGE_AI_TIMEOUT"),
        max_retries=_int_env("CONTRACTFORGE_AI_MAX_RETRIES"),
    )


def _deepseek_config(cls: type[ProviderConfig]) -> ProviderConfig:
    return cls(
        provider="deepseek",
        model=os.getenv("CONTRACTFORGE_AI_MODEL") or os.getenv("DEEPSEEK_MODEL"),
        api_key=os.getenv("CONTRACTFORGE_AI_API_KEY") or os.getenv("DEEPSEEK_API_KEY"),
        endpoint=os.getenv("CONTRACTFORGE_AI_ENDPOINT") or os.getenv("DEEPSEEK_BASE_URL"),
        timeout=_float_env("CONTRACTFORGE_AI_TIMEOUT"),
        max_retries=_int_env("CONTRACTFORGE_AI_MAX_RETRIES"),
    )


def _anthropic_config(cls: type[ProviderConfig]) -> ProviderConfig:
    return cls(
        provider="anthropic",
        model=os.getenv("CONTRACTFORGE_AI_MODEL") or os.getenv("ANTHROPIC_MODEL"),
        api_key=os.getenv("CONTRACTFORGE_AI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
        endpoint=os.getenv("CONTRACTFORGE_AI_ENDPOINT") or os.getenv("ANTHROPIC_BASE_URL"),
        api_version=os.getenv("CONTRACTFORGE_AI_API_VERSION") or os.getenv("ANTHROPIC_VERSION"),
        timeout=_float_env("CONTRACTFORGE_AI_TIMEOUT"),
        max_retries=_int_env("CONTRACTFORGE_AI_MAX_RETRIES"),
    )


def _gemini_config(cls: type[ProviderConfig]) -> ProviderConfig:
    return cls(
        provider="gemini",
        model=os.getenv("CONTRACTFORGE_AI_MODEL") or os.getenv("GEMINI_MODEL"),
        api_key=os.getenv("CONTRACTFORGE_AI_API_KEY") or os.getenv("GEMINI_API_KEY"),
        endpoint=os.getenv("CONTRACTFORGE_AI_ENDPOINT") or os.getenv("GEMINI_BASE_URL"),
        api_version=os.getenv("CONTRACTFORGE_AI_API_VERSION") or os.getenv("GEMINI_API_VERSION"),
        timeout=_float_env("CONTRACTFORGE_AI_TIMEOUT"),
        max_retries=_int_env("CONTRACTFORGE_AI_MAX_RETRIES"),
    )


def _bedrock_config(cls: type[ProviderConfig]) -> ProviderConfig:
    return cls(
        provider="bedrock",
        model=os.getenv("CONTRACTFORGE_AI_MODEL") or os.getenv("BEDROCK_MODEL_ID"),
        endpoint=os.getenv("CONTRACTFORGE_AI_ENDPOINT") or os.getenv("BEDROCK_ENDPOINT_URL"),
        api_version=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or os.getenv("BEDROCK_REGION"),
        timeout=_float_env("CONTRACTFORGE_AI_TIMEOUT"),
        max_retries=_int_env("CONTRACTFORGE_AI_MAX_RETRIES"),
    )


_PROVIDER_CONFIG_LOADERS: dict[str, ProviderConfigLoader] = {
    "offline": _offline_config,
    "openai": _openai_config,
    "azure_openai": _azure_openai_config,
    "databricks": _databricks_config,
    "deepseek": _deepseek_config,
    "anthropic": _anthropic_config,
    "gemini": _gemini_config,
    "bedrock": _bedrock_config,
}


def _float_env(name: str) -> float | None:
    value = os.getenv(name)
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ProviderConfigurationError(f"{name} must be a number") from exc


def _int_env(name: str) -> int | None:
    value = os.getenv(name)
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ProviderConfigurationError(f"{name} must be an integer") from exc
