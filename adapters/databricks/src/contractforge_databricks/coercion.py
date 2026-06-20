"""Small adapter-local coercion helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def mapping_list(value: object) -> list[dict[str, Any]]:
    return [dict(item) for item in value or () if isinstance(item, Mapping)]


def string_list(value: object, *, sep: str | None = None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(sep) if sep else (value,)
        return [item.strip() for item in items if item.strip()]
    if not isinstance(value, Iterable):
        return [str(value)]
    return [str(item).strip() for item in value if str(item).strip()]


def string_map(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item).lower() if isinstance(item, bool) else str(item) for key, item in value.items()}
