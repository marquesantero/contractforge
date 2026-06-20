"""AWS Bedrock model provider."""

from __future__ import annotations

import json
from typing import Any

from contractforge_ai.providers.base import (
    GenerationOptions,
    ProviderConfig,
    ProviderConfigurationError,
    ProviderExecutionError,
)

DEFAULT_TOOL_NAME = "contractforge_ai_response"


class BedrockProvider:
    """Provider backed by the AWS Bedrock Runtime Converse API."""

    name = "bedrock"

    def __init__(self, config: ProviderConfig, *, client: Any | None = None) -> None:
        self.config = _resolve_config(config)
        self.client = client if client is not None else self._build_client(self.config)

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        options: GenerationOptions | None = None,
    ) -> str:
        request = _payload(model=self.config.model, prompt=prompt, system=system, options=options)
        try:
            response = self.client.converse(**request)
        except Exception as exc:
            raise ProviderExecutionError(f"bedrock provider request failed: {exc}") from exc

        text = _extract_output_text(response)
        if text is None:
            raise ProviderExecutionError("bedrock provider returned a response without extractable output text.")
        return text

    @staticmethod
    def _build_client(config: ProviderConfig) -> Any:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise ProviderConfigurationError("Install contractforge-ai[aws] to use the AWS Bedrock provider.") from exc

        config_kwargs = {}
        if config.timeout is not None:
            config_kwargs["read_timeout"] = config.timeout
            config_kwargs["connect_timeout"] = config.timeout
        if config.max_retries is not None:
            config_kwargs["retries"] = {"max_attempts": config.max_retries}
        client_config = Config(**config_kwargs) if config_kwargs else None
        kwargs = {
            "service_name": "bedrock-runtime",
            "region_name": config.api_version,
            "endpoint_url": config.endpoint,
            "config": client_config,
        }
        return boto3.client(**{key: value for key, value in kwargs.items() if value is not None})


def _resolve_config(config: ProviderConfig) -> ProviderConfig:
    if not config.model:
        raise ProviderConfigurationError("Bedrock provider requires CONTRACTFORGE_AI_MODEL or BEDROCK_MODEL_ID.")
    return ProviderConfig(
        provider="bedrock",
        model=config.model,
        endpoint=config.endpoint,
        api_version=config.api_version,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )


def _payload(
    *,
    model: str | None,
    prompt: str,
    system: str | None,
    options: GenerationOptions | None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "modelId": model,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
    }
    if system:
        request["system"] = [{"text": system}]

    inference_config: dict[str, Any] = {}
    if options:
        if options.temperature is not None:
            inference_config["temperature"] = options.temperature
        if options.max_output_tokens is not None:
            inference_config["maxTokens"] = options.max_output_tokens
        if options.response_schema is not None:
            tool_name = options.response_schema_name or DEFAULT_TOOL_NAME
            request["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": tool_name,
                            "description": "Return the ContractForge AI response using this JSON schema.",
                            "inputSchema": {"json": _bedrock_json_schema(options.response_schema)},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": tool_name}},
            }
    if inference_config:
        request["inferenceConfig"] = inference_config
    return request


def _extract_output_text(response: dict[str, Any]) -> str | None:
    output = response.get("output")
    if not isinstance(output, dict):
        return None
    message = output.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None

    text_parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if isinstance(block.get("text"), str):
            text_parts.append(block["text"])
        tool_use = block.get("toolUse")
        if isinstance(tool_use, dict) and isinstance(tool_use.get("input"), dict):
            return json.dumps(tool_use["input"])

    if text_parts:
        return "\n".join(text_parts)
    return None


def _bedrock_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON Schema shape suitable for Bedrock tool inputSchema."""

    return _normalize_bedrock_schema(schema)


def _normalize_bedrock_schema(value: Any) -> Any:
    if isinstance(value, dict):
        converted = {}
        for key, item in value.items():
            if key == "const":
                converted["enum"] = [item]
            else:
                converted[key] = _normalize_bedrock_schema(item)
        return converted
    if isinstance(value, list):
        return [_normalize_bedrock_schema(item) for item in value]
    return value
