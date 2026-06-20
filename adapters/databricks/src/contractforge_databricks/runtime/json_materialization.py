"""JSON record materialization helpers for Databricks runtime connectors."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from typing import Any


def materialize_json_records(
    spark: Any,
    records: list[Any],
    *,
    schema: str | None = None,
    read_options: Mapping[str, Any] | None = None,
    staging_path: str | None = None,
) -> Any:
    if not records:
        return spark.createDataFrame([], schema or "value string").limit(0)
    normalized = [record if isinstance(record, Mapping) else {"value": record} for record in records]
    if hasattr(spark, "sparkContext") and hasattr(spark, "read"):
        json_lines = [json.dumps(record, default=str, ensure_ascii=False) for record in normalized]
        return _json_reader(spark, read_options, schema=schema).json(spark.sparkContext.parallelize(json_lines))
    staging_dir = _json_staging_dir(staging_path)
    if staging_dir and hasattr(spark, "read"):
        return _json_reader(spark, read_options, schema=schema).json(_write_json_lines_file(normalized, staging_dir))
    try:
        return _create_dataframe(spark, normalized, schema)
    except Exception as exc:
        if hasattr(spark, "read"):
            raise ValueError(
                "Could not materialize complex JSON records with createDataFrame. "
                "Declare source.read.staging_path or CONTRACTFORGE_SOURCE_JSON_STAGING_DIR with a local path "
                "accessible to the Python driver and Spark reader, or use source.response.mode=raw with shape.parse_json."
            ) from exc
        return _create_dataframe(spark, [_json_safe_record(record) for record in normalized], schema)


def _create_dataframe(spark: Any, records: list[Any], schema: str | None) -> Any:
    if schema is None:
        return spark.createDataFrame(records)
    try:
        return spark.createDataFrame(records, schema=schema)
    except TypeError as exc:
        if "schema" not in str(exc):
            raise
        return spark.createDataFrame(records, schema)


def _json_reader(spark: Any, options: Mapping[str, Any] | None, *, schema: str | None = None) -> Any:
    reader = spark.read
    if schema:
        reader = reader.schema(schema)
    if options is None:
        return reader
    if not isinstance(options, Mapping):
        raise ValueError("source.read.json_options must be an object")
    for key, value in options.items():
        option_key = str(key).strip()
        if not option_key:
            raise ValueError("source.read.json_options cannot contain an empty key")
        reader = reader.option(option_key, str(value).lower() if isinstance(value, bool) else str(value))
    return reader


def _json_staging_dir(staging_path: str | None) -> str | None:
    raw = str(staging_path or os.environ.get("CONTRACTFORGE_SOURCE_JSON_STAGING_DIR") or "").strip()
    if not raw:
        return None
    if "://" in raw and not raw.startswith("file:"):
        raise ValueError(
            "source.read.staging_path for JSON materialization must be a local filesystem path "
            "accessible to the Python driver and Spark reader, for example /Volumes/... or file:/..."
        )
    return raw


def _write_json_lines_file(records: list[Mapping[str, Any]], staging_dir: str) -> str:
    use_file_uri = staging_dir.startswith("file:")
    local_dir = staging_dir[5:] if use_file_uri else staging_dir
    os.makedirs(local_dir, exist_ok=True)
    path = os.path.join(local_dir, f"{uuid.uuid4().hex}.jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, default=str, ensure_ascii=False))
            handle.write("\n")
    return f"file:{path}" if use_file_uri else path


def _json_safe_record(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe_record(item) for key, item in value.items()}
    if isinstance(value, list):
        return json.dumps(value, default=str, ensure_ascii=False)
    return value
