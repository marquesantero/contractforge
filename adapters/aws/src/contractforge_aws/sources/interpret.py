"""Interpret core source intent for AWS Glue renderers."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import file_reader_options, file_source_format

BOOKMARK_ELIGIBLE_FORMATS = frozenset({"json", "csv", "parquet", "orc", "avro", "xml"})
_FILE_STREAM_SOURCE_TYPES = frozenset(
    {
        "avro",
        "csv",
        "json",
        "object_storage",
        "orc",
        "parquet",
        "s3",
        "xml",
    }
)


def is_incremental_file_source(source: dict[str, Any]) -> bool:
    source_type = str(source.get("type") or "")
    if source_type == "incremental_files":
        return True
    return source.get("intent") == "file_stream" and source_type in _FILE_STREAM_SOURCE_TYPES


def interpret_incremental_files_source(source: dict[str, Any]) -> dict[str, Any]:
    if not is_incremental_file_source(source):
        raise ValueError("AWS incremental file interpretation requires source.type incremental_files or source.intent file_stream")
    rendered = dict(source)
    rendered["type"] = "incremental_files"
    if not rendered.get("path"):
        raise ValueError("AWS file_stream source requires source.path")
    return rendered


def incremental_files_is_bookmark_renderable(source: dict[str, Any]) -> bool:
    """Return whether incremental files can map to a Glue bookmark read."""

    if not is_incremental_file_source(source):
        return False
    try:
        interpreted = interpret_incremental_files_source(source)
    except ValueError:
        return False
    try:
        return file_source_format(interpreted) in BOOKMARK_ELIGIBLE_FORMATS
    except ValueError:
        return False


def glue_incremental_file_format_options(source: dict[str, Any]) -> dict[str, Any]:
    """Translate portable reader options to Glue DynamicFrame format options."""

    source_format = file_source_format(source)
    options = file_reader_options(source)
    translator = _FORMAT_OPTION_TRANSLATORS.get(source_format, _identity_options)
    return translator(options)


def _csv_format_options(options: dict[str, Any]) -> dict[str, Any]:
    translated: dict[str, Any] = {}
    for key, value in sorted(options.items()):
        normalized = str(key).strip()
        target = _CSV_OPTION_ALIASES.get(normalized.lower(), normalized)
        if target in _CSV_IGNORED_SPARK_OPTIONS:
            continue
        translated[target] = _coerce_glue_option(value)
    return translated


def _identity_options(options: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _coerce_glue_option(value) for key, value in sorted(options.items())}


def _coerce_glue_option(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    text = str(value)
    lowered = text.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return value


_CSV_OPTION_ALIASES = {
    "header": "withHeader",
    "withheader": "withHeader",
    "delimiter": "separator",
    "sep": "separator",
    "quote": "quoteChar",
    "escape": "escaper",
}

_CSV_IGNORED_SPARK_OPTIONS = frozenset({"inferSchema", "infer_schema"})

_FORMAT_OPTION_TRANSLATORS = {
    "csv": _csv_format_options,
}
