"""Shared helpers for AWS Glue preparation renderers."""

from __future__ import annotations

from typing import Any


def as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item) for item in value or ()]
