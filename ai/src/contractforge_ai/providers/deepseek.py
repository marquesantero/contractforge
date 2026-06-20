"""DeepSeek model provider."""

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

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider:
    """Provider backed by DeepSeek's OpenAI-compatible Chat Completions API."""

    name = "deepseek"

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
            _chat_completions_url(self.config.endpoint),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self.http_client(request, timeout=self.config.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderExecutionError(f"deepseek provider request failed: HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise ProviderExecutionError(f"deepseek provider request failed: {exc}") from exc

        text = _extract_output_text(json.loads(raw))
        if text is None:
            raise ProviderExecutionError("deepseek provider returned a response without extractable output text.")
        return text


def _resolve_config(config: ProviderConfig) -> ProviderConfig:
    missing = []
    if not config.model:
        missing.append("CONTRACTFORGE_AI_MODEL or DEEPSEEK_MODEL")
    if not config.api_key:
        missing.append("CONTRACTFORGE_AI_API_KEY or DEEPSEEK_API_KEY")
    if missing:
        raise ProviderConfigurationError("DeepSeek provider requires: " + ", ".join(missing) + ".")

    return ProviderConfig(
        provider="deepseek",
        model=config.model,
        api_key=config.api_key,
        endpoint=config.endpoint or DEFAULT_DEEPSEEK_BASE_URL,
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
    payload: dict[str, Any] = {
        "model": model,
        "messages": _messages(system=system, prompt=prompt),
    }
    if options:
        if options.temperature is not None:
            payload["temperature"] = options.temperature
        if options.max_output_tokens is not None:
            payload["max_tokens"] = options.max_output_tokens
        if options.response_schema is not None:
            payload["response_format"] = {"type": "json_object"}
    return payload


def _chat_completions_url(base_url: str | None) -> str:
    if not base_url:
        raise ProviderConfigurationError("DeepSeek base URL is required.")
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _messages(*, system: str | None, prompt: str) -> list[dict[str, str]]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _extract_output_text(response: dict[str, Any]) -> str | None:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    return None
