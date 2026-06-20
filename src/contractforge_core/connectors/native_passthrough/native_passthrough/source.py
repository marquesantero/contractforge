"""Platform-neutral native passthrough source helpers."""

from __future__ import annotations

from typing import Any


def is_native_passthrough_source(source: dict[str, Any]) -> bool:
    return source.get("type") == "native_passthrough"


def native_passthrough_descriptor(source: dict[str, Any], *, redaction: str = "<redacted>") -> dict[str, Any]:
    if not is_native_passthrough_source(source):
        raise ValueError("native passthrough descriptor requires source.type native_passthrough")
    system = source.get("system")
    object_name = source.get("object")
    if not system or not object_name:
        raise ValueError("native_passthrough requires system and object")
    return {
        "system": system,
        "object": object_name,
        "watermark": source.get("watermark", {}),
        "auth": redact_secret_fields(source.get("auth", {}), redaction=redaction),
    }


def redact_secret_fields(values: dict[str, Any], *, redaction: str = "<redacted>") -> dict[str, Any]:
    redacted = {}
    for key, value in values.items():
        normalized = key.lower()
        if "secret" in normalized or "token" in normalized or "password" in normalized:
            redacted[key] = redaction
        else:
            redacted[key] = value
    return redacted
