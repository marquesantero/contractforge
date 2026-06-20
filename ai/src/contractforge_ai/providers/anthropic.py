"""Anthropic model provider."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from contractforge_ai.providers.base import (
    GenerationOptions,
    ProviderConfig,
    ProviderConfigurationError,
    ProviderExecutionError,
)

DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_OUTPUT_TOKENS = 1024


class AnthropicProvider:
    """Provider backed by Anthropic's Messages API."""

    name = "anthropic"

    def __init__(self, config: ProviderConfig, *, http_client: Any | None = None) -> None:
        self.config = _resolve_config(config)
        self.http_client = http_client or urllib.request.urlopen

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        options: GenerationOptions | None = None,
    ) -> str:
        payload = _payload(model=self.config.model, prompt=prompt, system=system, options=options)
        request = urllib.request.Request(
            _messages_url(self.config.endpoint),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": str(self.config.api_key),
                "anthropic-version": str(self.config.api_version),
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self.http_client(request, timeout=self.config.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderExecutionError(f"anthropic provider request failed: HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise ProviderExecutionError(f"anthropic provider request failed: {exc}") from exc

        text = _extract_output_text(json.loads(raw))
        if text is None:
            raise ProviderExecutionError("anthropic provider returned a response without extractable output text.")
        return text


def _resolve_config(config: ProviderConfig) -> ProviderConfig:
    missing = []
    if not config.model:
        missing.append("CONTRACTFORGE_AI_MODEL or ANTHROPIC_MODEL")
    if not config.api_key:
        missing.append("CONTRACTFORGE_AI_API_KEY or ANTHROPIC_API_KEY")
    if missing:
        raise ProviderConfigurationError("Anthropic provider requires: " + ", ".join(missing) + ".")

    return ProviderConfig(
        provider="anthropic",
        model=config.model,
        api_key=config.api_key,
        endpoint=config.endpoint or DEFAULT_ANTHROPIC_BASE_URL,
        api_version=config.api_version or DEFAULT_ANTHROPIC_VERSION,
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
    max_tokens = options.max_output_tokens if options and options.max_output_tokens is not None else DEFAULT_MAX_OUTPUT_TOKENS
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    if options:
        if options.temperature is not None:
            payload["temperature"] = options.temperature
        if options.response_schema is not None:
            tool_name = options.response_schema_name or "contractforge_ai_response"
            payload["tools"] = [
                {
                    "name": tool_name,
                    "description": "Return the ContractForge AI response using this JSON schema.",
                    "input_schema": options.response_schema,
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": tool_name}
    return payload


def _messages_url(base_url: str | None) -> str:
    if not base_url:
        raise ProviderConfigurationError("Anthropic base URL is required.")
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1/messages"):
        return normalized
    return f"{normalized}/v1/messages"


def _extract_output_text(response: dict[str, Any]) -> str | None:
    content = response.get("content")
    if not isinstance(content, list):
        return None

    text_parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use" and isinstance(block.get("input"), dict):
            return json.dumps(block["input"])
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            text_parts.append(block["text"])

    if text_parts:
        return "\n".join(text_parts)
    return None
