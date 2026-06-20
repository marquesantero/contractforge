"""Databricks runtime execution for bounded HTTP file sources."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import (
    cleanup_http_file_downloads as cleanup_http_file_downloads,
    download_http_file,
    http_file_format,
    http_file_reader_options,
    is_http_file_source,
)
from contractforge_databricks.runtime.source_schema import apply_declared_schema


def resolve_http_file_dataframe(spark: Any, source: dict[str, Any]) -> Any:
    """Download a bounded HTTP file and load it with Spark's native reader."""

    if not is_http_file_source(source):
        raise ValueError("HTTP file runtime resolution requires source.type http_file/http_csv/http_json/http_text")
    local_path = download_http_file(source)
    reader = spark.read.format(http_file_format(source))
    for key, value in sorted(http_file_reader_options(source).items()):
        reader = reader.option(key, value)
    reader = apply_declared_schema(reader, source)
    df = reader.load(local_path)
    _enforce_max_records(df, source)
    return df

def _enforce_max_records(df: Any, source: dict[str, Any]) -> None:
    max_records = source.get("limits", {}).get("max_records")
    if max_records is None or not hasattr(df, "count"):
        return
    count = int(df.count())
    if count > int(max_records):
        raise ValueError(f"HTTP file response exceeds source.limits.max_records={int(max_records)}")
