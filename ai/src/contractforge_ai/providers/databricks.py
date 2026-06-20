"""Databricks Model Serving provider."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from contractforge_ai.providers.base import (
    GenerationOptions,
    ProviderConfig,
    ProviderConfigurationError,
    ProviderExecutionError,
)


class DatabricksModelServingProvider:
    """Provider backed by Databricks Model Serving endpoint invocations."""

    name = "databricks"

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
        payload: dict[str, Any] = {
            "messages": _messages(system=system, prompt=prompt),
        }
        if options:
            if options.temperature is not None:
                payload["temperature"] = options.temperature
            if options.max_output_tokens is not None:
                payload["max_tokens"] = options.max_output_tokens

        request = urllib.request.Request(
            _endpoint_url(self.config.endpoint, self.config.model),
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
            raise ProviderExecutionError(f"databricks provider request failed: HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise ProviderExecutionError(f"databricks provider request failed: {exc}") from exc

        text = _extract_output_text(json.loads(raw))
        if text is None:
            raise ProviderExecutionError("databricks provider returned a response without extractable output text.")
        return text


def _resolve_config(config: ProviderConfig) -> ProviderConfig:
    host = config.endpoint
    token = config.api_key
    if not host or not token:
        notebook_host, notebook_token = _notebook_context_auth()
        host = host or notebook_host
        token = token or notebook_token

    missing = []
    if not config.model:
        missing.append("CONTRACTFORGE_AI_MODEL or DATABRICKS_SERVING_ENDPOINT")
    if not host:
        missing.append("CONTRACTFORGE_AI_ENDPOINT or DATABRICKS_HOST")
    if not token:
        missing.append("CONTRACTFORGE_AI_API_KEY or DATABRICKS_TOKEN")
    if missing:
        raise ProviderConfigurationError("Databricks provider requires: " + ", ".join(missing) + ".")

    return ProviderConfig(
        provider="databricks",
        model=config.model,
        api_key=token,
        endpoint=host,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )


def _endpoint_url(host: str | None, endpoint_name: str | None) -> str:
    if not host or not endpoint_name:
        raise ProviderConfigurationError("Databricks host and serving endpoint are required.")
    if endpoint_name.startswith("https://"):
        return endpoint_name
    normalized_host = host.rstrip("/")
    return f"{normalized_host}/serving-endpoints/{endpoint_name}/invocations"


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

    for key in ("output_text", "text", "response", "result"):
        value = response.get(key)
        if isinstance(value, str):
            return value

    predictions = response.get("predictions")
    if isinstance(predictions, list) and predictions:
        first = predictions[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("text", "output_text", "response", "result"):
                value = first.get(key)
                if isinstance(value, str):
                    return value
    return None


def _notebook_context_auth() -> tuple[str | None, str | None]:
    if not os.getenv("DATABRICKS_RUNTIME_VERSION"):
        return None, None
    try:
        from databricks.sdk.runtime import dbutils

        context = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
        host = context.apiUrl().get()
        token = context.apiToken().get()
        return host, token
    except Exception:
        return None, None
