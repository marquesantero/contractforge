"""Databricks source connector classification.

This module is adapter-owned: it maps portable core connector semantics to the
Databricks rendering/runtime surface without making Databricks names portable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.connectors import (
    JDBC_CONNECTORS,
    is_bounded_stream_source,
    is_catalog_source,
    is_delta_share_source,
    is_file_source,
    is_http_file_source,
    is_native_passthrough_source,
    is_rest_api_connector,
)
from contractforge_databricks.sources.interpret import is_incremental_file_source

SUPPORTED = "SUPPORTED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class DatabricksSourceClassification:
    source_type: str
    status: str
    native_mapping: str | None
    note: str


def classify_databricks_source(source: dict[str, Any] | str) -> DatabricksSourceClassification:
    """Classify a source connector against Databricks support semantics."""

    payload = {"type": source} if isinstance(source, str) else dict(source)
    source_type = str(payload.get("connector") or payload.get("type") or "").strip().lower()
    if is_incremental_file_source(payload):
        return DatabricksSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="Auto Loader cloudFiles",
            note="Uses core incremental_files/file_stream intent.",
        )
    if _is_jdbc_source(payload):
        return DatabricksSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="Spark JDBC reader",
            note="Core builds JDBC options; Databricks resolves secrets.",
        )
    if is_catalog_source(payload):
        return DatabricksSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="spark.table / spark.sql",
            note="Catalog resolution is runtime-owned.",
        )
    if is_http_file_source(payload):
        return DatabricksSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="Core HTTP file fetch + Spark reader",
            note="Fetch algorithm lives in core.",
        )
    if is_rest_api_connector(payload):
        return DatabricksSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="Core REST client + Spark JSON materialization",
            note="Secrets resolve in Databricks.",
        )
    if source_type == "custom_transform":
        return DatabricksSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="Databricks notebook task in Asset Bundle",
            note="Contract declares inputs; Databricks binds the reviewed treatment notebook.",
        )
    if is_bounded_stream_source(payload):
        return DatabricksSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="Spark bounded kafka/eventhubs reader",
            note="Not continuous streaming.",
        )
    if is_delta_share_source(payload):
        return DatabricksSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="Delta Sharing Spark connector",
            note="Runtime must provide connector support.",
        )
    if is_file_source(payload):
        return DatabricksSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="Spark file reader",
            note="Format and reader options are core-normalized.",
        )
    if is_native_passthrough_source(payload):
        return DatabricksSourceClassification(
            source_type=source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Databricks native connector handoff",
            note="Adapter-owned design review.",
        )
    return DatabricksSourceClassification(
        source_type=source_type,
        status=UNSUPPORTED,
        native_mapping=None,
        note="No Databricks source renderer is declared for this connector.",
    )


def _is_jdbc_source(source: dict[str, Any]) -> bool:
    connector = source.get("connector") or source.get("type")
    return connector in JDBC_CONNECTORS or source.get("type") == "jdbc"
