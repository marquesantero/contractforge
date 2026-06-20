"""Databricks runtime source metadata helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import source_metadata_from_mapping


def source_name(source: dict[str, Any]) -> str:
    return str(source.get("table") or source.get("path") or source.get("url") or source.get("type") or "source")


def source_metadata(source: dict[str, Any]) -> dict[str, Any]:
    return source_metadata_from_mapping(source)


def schema_types(df: Any) -> dict[str, str] | None:
    schema = getattr(df, "schema", None)
    fields = getattr(schema, "fields", None)
    if not fields:
        return None
    return {str(field.name): str(field.dataType.simpleString()) for field in fields}


def source_metadata_with_watermark(source: dict[str, Any], watermark_previous: str | None) -> dict[str, Any]:
    metadata = source_metadata(source)
    if watermark_previous is not None:
        metadata["watermark_previous"] = watermark_previous
    return metadata
