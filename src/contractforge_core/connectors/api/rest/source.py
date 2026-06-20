"""REST API connector detection and review descriptor."""

from __future__ import annotations

from typing import Any

REST_API_CONNECTORS = frozenset({"rest_api", "api", "http_api"})


def is_rest_api_connector(source: dict[str, Any]) -> bool:
    return source.get("type") in REST_API_CONNECTORS or (
        source.get("type") == "connector" and source.get("connector") in REST_API_CONNECTORS
    )


def rest_api_descriptor(source: dict[str, Any], *, redaction: str = "<redacted>") -> dict[str, Any]:
    if not is_rest_api_connector(source):
        raise ValueError(
            "REST API descriptor requires source.type=rest_api or source.type=connector and connector=rest_api"
        )
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    response = source.get("response") if isinstance(source.get("response"), dict) else {}
    pagination = source.get("pagination") if isinstance(source.get("pagination"), dict) else {}
    return {
        "source_name": source.get("name") or source.get("connector"),
        "url": source.get("url") or request.get("url"),
        "method": request.get("method", "GET"),
        "pagination": pagination,
        "incremental": source.get("incremental", {}),
        "response": response,
        "auth": _redact_secret_fields(source.get("auth", {}), redaction=redaction),
    }


def _redact_secret_fields(values: dict[str, Any], *, redaction: str = "<redacted>") -> dict[str, Any]:
    redacted = {}
    for key, value in values.items():
        normalized = key.lower()
        if "secret" in normalized or "token" in normalized or "password" in normalized:
            redacted[key] = redaction
        else:
            redacted[key] = value
    return redacted
