"""Source type portability classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourcePortability = Literal[
    "PORTABLE_BUILTIN",
    "BOUNDED_STREAM",
    "AVAILABLE_NOW_STREAM",
    "NATIVE_PASSTHROUGH",
    "UNSUPPORTED",
]


@dataclass(frozen=True)
class SourceTypeClassification:
    source_type: str
    portability: SourcePortability
    reason: str
    adapter: str | None = None


PORTABLE_SOURCE_TYPES = {
    "table",
    "delta_table",
    "iceberg_table",
    "view",
    "sql",
    "csv",
    "json",
    "jsonl",
    "ndjson",
    "parquet",
    "delta",
    "orc",
    "text",
    "avro",
    "xml",
    "s3",
    "adls",
    "azure_blob",
    "gcs",
    "blob",
    "object_storage",
    "connection",
    "incremental_files",
    "http_file",
    "http_csv",
    "http_json",
    "http_text",
    "jdbc",
    "postgres",
    "mysql",
    "sqlserver",
    "oracle",
    "redshift",
    "db2",
    "mariadb",
    "snowflake_jdbc",
    "bigquery_jdbc",
    "delta_share",
    "rest_api",
}

BOUNDED_STREAM_SOURCE_TYPES = {"kafka_bounded", "eventhubs_bounded"}

AVAILABLE_NOW_STREAM_SOURCE_TYPES = {"kafka_available_now", "eventhubs_available_now"}

NATIVE_PASSTHROUGH_SOURCE_TYPES = {"native_passthrough"}


def classify_source_type(source_type: str) -> SourceTypeClassification:
    normalized = str(source_type or "").strip().lower()
    if normalized in PORTABLE_SOURCE_TYPES:
        return SourceTypeClassification(normalized, "PORTABLE_BUILTIN", "Portable source intent.")
    if normalized in BOUNDED_STREAM_SOURCE_TYPES:
        return SourceTypeClassification(normalized, "BOUNDED_STREAM", "Bounded replay/catch-up source intent.")
    if normalized in AVAILABLE_NOW_STREAM_SOURCE_TYPES:
        return SourceTypeClassification(
            normalized,
            "AVAILABLE_NOW_STREAM",
            "Checkpointed available-now stream catch-up source intent.",
        )
    if normalized in NATIVE_PASSTHROUGH_SOURCE_TYPES:
        return SourceTypeClassification(normalized, "NATIVE_PASSTHROUGH", "Adapter-owned native connector intent.")
    return SourceTypeClassification(normalized, "UNSUPPORTED", "Unknown source type.")
