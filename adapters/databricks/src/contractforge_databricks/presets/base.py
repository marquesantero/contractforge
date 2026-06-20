"""Shared Databricks preset metadata helpers."""

from __future__ import annotations

from typing import Any

Preset = dict[str, Any]
PRESET_META_KEY = "_preset"


def meta(
    name: str,
    category: str,
    kind: str,
    description: str,
    required_fields: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "category": category,
        "kind": kind,
        "required_fields": list(required_fields or []),
    }
