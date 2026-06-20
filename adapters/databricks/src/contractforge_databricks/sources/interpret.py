"""Interpret core source contracts for Databricks renderers."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.environment import DatabricksEnvironment

_FILE_STREAM_SOURCE_TYPES = {
    "adls",
    "avro",
    "azure_blob",
    "blob",
    "csv",
    "delta",
    "gcs",
    "json",
    "object_storage",
    "orc",
    "parquet",
    "s3",
    "text",
    "xml",
}


def is_incremental_file_source(source: dict[str, Any]) -> bool:
    source_type = str(source.get("type") or "")
    if source_type == "incremental_files":
        return True
    return source.get("intent") == "file_stream" and source_type in _FILE_STREAM_SOURCE_TYPES


def interpret_incremental_files_source(
    source: dict[str, Any],
    *,
    environment: DatabricksEnvironment | None = None,
) -> dict[str, Any]:
    if not is_incremental_file_source(source):
        raise ValueError("incremental file interpretation requires source.type incremental_files or source.intent file_stream")
    rendered = dict(source)
    rendered["type"] = "incremental_files"
    if not rendered.get("path"):
        raise ValueError("Databricks file_stream source requires source.path")
    options = _options(source)
    params = (environment.parameters if environment else {}) or {}
    state = source.get("state") if isinstance(source.get("state"), dict) else {}
    state_location = state.get("location") if isinstance(state.get("location"), dict) else {}

    if not rendered.get("progress_location") and state_location.get("type") == "object_storage" and state_location.get("path"):
        rendered["progress_location"] = state_location["path"]

    _set_bool_option(options, "cloudFiles.inferColumnTypes", source.get("options", {}).get("infer_column_types"))
    _set_bool_option(options, "cloudFiles.inferColumnTypes", params.get("incremental_files.infer_column_types"))
    _set_if_present(options, "cloudFiles.maxFilesPerTrigger", source.get("max_files_per_trigger"))
    _set_if_present(options, "cloudFiles.maxFilesPerTrigger", params.get("incremental_files.max_files_per_trigger"))

    rendered["options"] = options
    return rendered


def _options(source: dict[str, Any]) -> dict[str, str]:
    raw = source.get("options") if isinstance(source.get("options"), dict) else {}
    ignored = {"infer_column_types"}
    return {str(key): str(value) for key, value in raw.items() if key not in ignored}


def _set_bool_option(options: dict[str, str], key: str, value: object) -> None:
    if value is None:
        return
    options[key] = str(bool(value)).lower() if isinstance(value, bool) else str(value)


def _set_if_present(options: dict[str, str], key: str, value: object) -> None:
    if value is not None:
        options[key] = str(value)
