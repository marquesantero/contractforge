"""OpenAI-compatible model providers."""

from __future__ import annotations

from typing import Any

from contractforge_ai.providers.base import (
    GenerationOptions,
    ProviderConfig,
    ProviderConfigurationError,
    ProviderExecutionError,
)


class OpenAIProvider:
    """Provider backed by the OpenAI Responses API."""

    name = "openai"

    def __init__(self, config: ProviderConfig, *, client: Any | None = None) -> None:
        self.config = _require_model(config)
        self.client = client if client is not None else self._build_client(self.config)

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        options: GenerationOptions | None = None,
    ) -> str:
        return _responses_complete(
            self.client,
            model=self.config.model,
            prompt=prompt,
            system=system,
            options=options,
            provider_name=self.name,
        )

    @staticmethod
    def _build_client(config: ProviderConfig) -> Any:
        if not config.api_key:
            raise ProviderConfigurationError("OpenAI provider requires OPENAI_API_KEY or CONTRACTFORGE_AI_API_KEY.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderConfigurationError("Install contractforge-ai[openai] to use the OpenAI provider.") from exc

        kwargs = {
            "api_key": config.api_key,
            "organization": config.organization,
            "project": config.project,
            "timeout": config.timeout,
            "max_retries": config.max_retries,
        }
        return OpenAI(**{key: value for key, value in kwargs.items() if value is not None})


class AzureOpenAIProvider:
    """Provider backed by Azure OpenAI using the OpenAI SDK."""

    name = "azure_openai"

    def __init__(self, config: ProviderConfig, *, client: Any | None = None) -> None:
        self.config = _require_model(config)
        self.client = client if client is not None else self._build_client(self.config)

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        options: GenerationOptions | None = None,
    ) -> str:
        return _responses_complete(
            self.client,
            model=self.config.model,
            prompt=prompt,
            system=system,
            options=options,
            provider_name=self.name,
        )

    @staticmethod
    def _build_client(config: ProviderConfig) -> Any:
        missing = []
        if not config.api_key:
            missing.append("AZURE_OPENAI_API_KEY or CONTRACTFORGE_AI_API_KEY")
        if not config.endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT or CONTRACTFORGE_AI_ENDPOINT")
        if not config.api_version:
            missing.append("AZURE_OPENAI_API_VERSION or CONTRACTFORGE_AI_API_VERSION")
        if missing:
            raise ProviderConfigurationError("Azure OpenAI provider requires: " + ", ".join(missing) + ".")

        try:
            from openai import AzureOpenAI
        except ImportError as exc:
            raise ProviderConfigurationError("Install contractforge-ai[openai] to use the Azure OpenAI provider.") from exc

        kwargs = {
            "api_key": config.api_key,
            "azure_endpoint": config.endpoint,
            "api_version": config.api_version,
            "timeout": config.timeout,
            "max_retries": config.max_retries,
        }
        return AzureOpenAI(**{key: value for key, value in kwargs.items() if value is not None})


def _responses_complete(
    client: Any,
    *,
    model: str | None,
    prompt: str,
    system: str | None,
    options: GenerationOptions | None,
    provider_name: str,
) -> str:
    request: dict[str, Any] = {
        "model": model,
        "input": prompt,
    }
    if system:
        request["instructions"] = system
    if options:
        if options.temperature is not None:
            request["temperature"] = options.temperature
        if options.max_output_tokens is not None:
            request["max_output_tokens"] = options.max_output_tokens
        if options.response_schema is not None:
            request["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": options.response_schema_name or "contractforge_ai_output",
                    "schema": _openai_json_schema(options.response_schema),
                    "strict": options.response_schema_strict,
                }
            }

    try:
        response = client.responses.create(**request)
    except Exception as exc:
        raise ProviderExecutionError(f"{provider_name} provider request failed: {exc}") from exc

    text = _extract_output_text(response)
    if text is None:
        raise ProviderExecutionError(f"{provider_name} provider returned a response without extractable output text.")
    return text


def _extract_output_text(response: Any) -> str | None:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text

    if isinstance(response, dict):
        data = response
    elif hasattr(response, "model_dump"):
        data = response.model_dump()
    else:
        return None

    chunks: list[str] = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            if isinstance(content, dict):
                if isinstance(content.get("text"), str):
                    chunks.append(content["text"])
                elif isinstance(content.get("output_text"), str):
                    chunks.append(content["output_text"])
    return "\n".join(chunks) if chunks else None


def _openai_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON Schema shape accepted by OpenAI structured outputs."""

    return _normalize_openai_schema(schema)


def _normalize_openai_schema(value: Any) -> Any:
    if isinstance(value, dict):
        converted = {}
        for key, item in value.items():
            if key == "const":
                converted["enum"] = [item]
            else:
                converted[key] = _normalize_openai_schema(item)
        if converted.get("type") == "object" and isinstance(converted.get("properties"), dict):
            converted["required"] = list(converted["properties"].keys())
        return converted
    if isinstance(value, list):
        return [_normalize_openai_schema(item) for item in value]
    return value


def _require_model(config: ProviderConfig) -> ProviderConfig:
    if not config.model:
        raise ProviderConfigurationError(f"{config.provider} provider requires CONTRACTFORGE_AI_MODEL.")
    return config
