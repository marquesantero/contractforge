"""Google Gemini API provider."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from contractforge_ai.providers.base import (
    GenerationOptions,
    ProviderConfig,
    ProviderConfigurationError,
    ProviderExecutionError,
)

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_GEMINI_API_VERSION = "v1beta"


class GeminiProvider:
    """Provider backed by the Google Gemini generateContent API."""

    name = "gemini"

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
        payload = _payload(prompt=prompt, system=system, options=options)
        request = urllib.request.Request(
            _generate_content_url(
                base_url=self.config.endpoint,
                api_version=self.config.api_version,
                model=self.config.model,
            ),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-goog-api-key": str(self.config.api_key),
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self.http_client(request, timeout=self.config.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderExecutionError(f"gemini provider request failed: HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise ProviderExecutionError(f"gemini provider request failed: {exc}") from exc

        text = _extract_output_text(json.loads(raw))
        if text is None:
            raise ProviderExecutionError("gemini provider returned a response without extractable output text.")
        return text


def _resolve_config(config: ProviderConfig) -> ProviderConfig:
    missing = []
    if not config.model:
        missing.append("CONTRACTFORGE_AI_MODEL or GEMINI_MODEL")
    if not config.api_key:
        missing.append("CONTRACTFORGE_AI_API_KEY or GEMINI_API_KEY")
    if missing:
        raise ProviderConfigurationError("Gemini provider requires: " + ", ".join(missing) + ".")

    return ProviderConfig(
        provider="gemini",
        model=config.model,
        api_key=config.api_key,
        endpoint=config.endpoint or DEFAULT_GEMINI_BASE_URL,
        api_version=config.api_version or DEFAULT_GEMINI_API_VERSION,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )


def _payload(
    *,
    prompt: str,
    system: str | None,
    options: GenerationOptions | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    generation_config: dict[str, Any] = {}
    if options:
        if options.temperature is not None:
            generation_config["temperature"] = options.temperature
        if options.max_output_tokens is not None:
            generation_config["maxOutputTokens"] = options.max_output_tokens
        if options.response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseJsonSchema"] = _gemini_json_schema(options.response_schema)
    if generation_config:
        payload["generationConfig"] = generation_config
    return payload


def _generate_content_url(*, base_url: str | None, api_version: str | None, model: str | None) -> str:
    if not base_url:
        raise ProviderConfigurationError("Gemini base URL is required.")
    if not model:
        raise ProviderConfigurationError("Gemini model is required.")

    normalized = base_url.rstrip("/")
    if normalized.endswith(":generateContent"):
        return normalized

    version = (api_version or DEFAULT_GEMINI_API_VERSION).strip("/")
    if not normalized.endswith(f"/{version}"):
        normalized = f"{normalized}/{version}"

    model_path = model if model.startswith(("models/", "tunedModels/")) else f"models/{model}"
    encoded_model_path = urllib.parse.quote(model_path, safe="/")
    return f"{normalized}/{encoded_model_path}:generateContent"


def _extract_output_text(response: dict[str, Any]) -> str | None:
    candidates = response.get("candidates")
    if not isinstance(candidates, list):
        return None

    text_parts: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text_parts.append(part["text"])

    if text_parts:
        return "\n".join(text_parts)
    return None


def _gemini_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON Schema shape suitable for Gemini native structured output."""

    return _normalize_gemini_schema(schema)


def _normalize_gemini_schema(value: Any) -> Any:
    if isinstance(value, dict):
        converted = {}
        for key, item in value.items():
            if key == "const":
                converted["enum"] = [item]
            else:
                converted[key] = _normalize_gemini_schema(item)
        return converted
    if isinstance(value, list):
        return [_normalize_gemini_schema(item) for item in value]
    return value
