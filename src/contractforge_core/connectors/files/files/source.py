"""File and object-storage source helpers."""

from __future__ import annotations

from typing import Any

FILE_SOURCE_TYPES = frozenset({"csv", "json", "jsonl", "ndjson", "parquet", "delta", "orc", "text", "avro", "xml"})
OBJECT_STORAGE_TYPES = frozenset({"s3", "adls", "azure_blob", "gcs", "blob", "object_storage"})


def is_file_source(source: dict[str, Any]) -> bool:
    source_type = source.get("type")
    connector = source.get("connector")
    return source_type in FILE_SOURCE_TYPES or source_type in OBJECT_STORAGE_TYPES or connector in FILE_SOURCE_TYPES | OBJECT_STORAGE_TYPES


def file_source_format(source: dict[str, Any]) -> str:
    source_type = source.get("type")
    connector = source.get("connector")
    declared = source.get("format")
    if declared:
        return normalize_file_format(str(declared))
    if source_type in FILE_SOURCE_TYPES:
        return normalize_file_format(str(source_type))
    if connector in FILE_SOURCE_TYPES:
        return normalize_file_format(str(connector))
    raise ValueError("file/object storage source requires format")


def file_reader_options(source: dict[str, Any]) -> dict[str, str]:
    return {str(key): _option_value(value) for key, value in source.get("options", {}).items() if key != "schema"}


def normalize_file_format(value: str) -> str:
    return "json" if value in {"jsonl", "ndjson"} else value


def object_storage_provider(source: dict[str, Any]) -> str | None:
    source_type = source.get("type")
    connector = source.get("connector")
    provider = source.get("provider")
    if provider:
        return str(provider)
    if source_type in OBJECT_STORAGE_TYPES:
        return str(source_type)
    if connector in OBJECT_STORAGE_TYPES:
        return str(connector)
    return None


def _option_value(value: object) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)
