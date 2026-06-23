"""Databricks source connector support declarations."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.sources.classification import (
    DatabricksSourceClassification,
    classify_databricks_source,
)


def databricks_source_support(source: dict[str, Any] | str) -> dict[str, Any]:
    """Return Databricks support metadata for a source connector.

    This is adapter-owned documentation data. It does not affect core planning
    and does not make Databricks names portable.
    """

    return _entry(classify_databricks_source(source))


def list_databricks_source_support() -> tuple[dict[str, Any], ...]:
    sources = (
        "table",
        "sql",
        "csv",
        "s3",
        "incremental_files",
        "http_json",
        "rest_api",
        "custom_transform",
        "jdbc",
        "kafka_bounded",
        "eventhubs_bounded",
        "delta_share",
        "native_passthrough",
    )
    return tuple(databricks_source_support(source) for source in sources)


def _entry(classification: DatabricksSourceClassification) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "adapter": "databricks",
        "source_type": classification.source_type,
        "status": classification.status,
        "note": classification.note,
    }
    if classification.native_mapping:
        entry["native_mapping"] = classification.native_mapping
    return entry
