"""Shared normalization helpers."""

from __future__ import annotations

from typing import Any


def validated_choice(value: str, valid: set[str], field_name: str) -> str:
    raw = str(value).strip()
    if raw not in valid:
        raise ValueError(f"Unsupported {field_name}: {raw}. Valid values: {sorted(valid)}")
    return raw


def as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def nested_shape(transform: Any) -> Any:
    if isinstance(transform, dict):
        return transform.get("shape")
    return None
