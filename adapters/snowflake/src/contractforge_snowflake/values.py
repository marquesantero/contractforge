"""Small value-coercion helpers shared by Snowflake modules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def dict_mapping(value: object) -> dict[str, Any]:
    """Return a defensive dict for dict-shaped contract sections."""

    return dict(value) if isinstance(value, dict) else {}


def mapping_view(value: object) -> Mapping[str, Any]:
    """Return a read-only-style mapping view for mapping-shaped settings."""

    return value if isinstance(value, Mapping) else {}


def string_or_none(value: object | None) -> str | None:
    return None if value is None else str(value)


def text_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def string_list(value: object, *, separator: str | None = None, strip: bool = False) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(separator) if separator else [value]
    else:
        items = value  # type: ignore[assignment]
    result: list[str] = []
    for item in items:  # type: ignore[union-attr]
        text = str(item)
        if strip:
            text = text.strip()
            if not text:
                continue
        result.append(text)
    return result


def pipe_string_list(value: object) -> list[str]:
    return string_list(value, separator="|", strip=True)


__all__ = ["dict_mapping", "mapping_view", "pipe_string_list", "string_list", "string_or_none", "text_bool"]
