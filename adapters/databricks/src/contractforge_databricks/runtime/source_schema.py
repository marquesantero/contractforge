"""Runtime source schema helpers for Databricks readers."""

from __future__ import annotations

from typing import Any


def source_declared_schema(source: dict[str, Any]) -> str | None:
    if source.get("schema") not in (None, ""):
        raise ValueError("source.schema is not supported; declare source.read.schema")
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    values = [read.get("schema"), options.get("schema")]
    declared = [str(value).strip() for value in values if value not in (None, "")]
    if len(set(declared)) > 1:
        raise ValueError("source.read.schema conflicts with source.options.schema")
    if declared and not declared[0]:
        raise ValueError("source.read.schema cannot be empty")
    return declared[0] if declared else None


def apply_declared_schema(reader: Any, source: dict[str, Any]) -> Any:
    schema = source_declared_schema(source)
    return reader.schema(schema) if schema else reader
