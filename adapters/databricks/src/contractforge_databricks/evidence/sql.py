"""Render INSERT statements for Databricks evidence tables."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from contractforge_core.evidence import (
    AccessEvidenceRecord,
    CostEvidenceRecord,
    ErrorEvidenceRecord,
    LineageEvidenceRecord,
    QualityEvidenceRecord,
    QuarantineEvidenceRecord,
    RunEvidenceRecord,
    SchemaChangeEvidenceRecord,
    SourceMetadataEvidenceRecord,
    StreamBatchEvidenceRecord,
)
from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.sql import quote_table_name


def render_run_insert_sql(record: RunEvidenceRecord, *, catalog: str = "main", schema: str = "ops") -> str:
    table = evidence_table_names(catalog, schema)["runs"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, mode, status, started_at_utc, finished_at_utc, metrics_json) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_s(record.mode)}, {_s(record.status)}, "
        f"{_ts(record.started_at_utc)}, {_ts(record.finished_at_utc)}, {_json(record.metrics or {})})"
    )


def render_error_insert_sql(record: ErrorEvidenceRecord, *, catalog: str = "main", schema: str = "ops") -> str:
    table = evidence_table_names(catalog, schema)["errors"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, error_class, error_message, occurred_at_utc) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_s(record.error_class)}, {_s(record.error_message)}, "
        f"{_ts(record.occurred_at_utc)})"
    )


def render_lineage_insert_sql(record: LineageEvidenceRecord, *, catalog: str = "main", schema: str = "ops") -> str:
    table = evidence_table_names(catalog, schema)["lineage"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, source_name, event_json, event_time_utc) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_s(record.source_name)}, {_json(record.event)}, "
        f"{_ts(record.event_time_utc)})"
    )


def render_quality_insert_sql(record: QualityEvidenceRecord, *, catalog: str = "main", schema: str = "ops") -> str:
    table = evidence_table_names(catalog, schema)["quality"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, rule_name, status, observed_value, checked_at_utc) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_s(record.rule_name)}, {_s(record.status)}, "
        f"{_s(record.observed_value)}, {_ts(record.checked_at_utc)})"
    )


def render_schema_change_insert_sql(
    record: SchemaChangeEvidenceRecord, *, catalog: str = "main", schema: str = "ops"
) -> str:
    table = evidence_table_names(catalog, schema)["schema_changes"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, change_type, payload_json, changed_at_utc) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_s(record.change_type)}, {_json(record.payload)}, "
        f"{_ts(record.changed_at_utc)})"
    )


def render_cost_insert_sql(record: CostEvidenceRecord, *, catalog: str = "main", schema: str = "ops") -> str:
    table = evidence_table_names(catalog, schema)["cost"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, signal_name, signal_value, payload_json, captured_at_utc) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_s(record.signal_name)}, {record.signal_value}, "
        f"{_json(record.payload)}, {_ts(record.captured_at_utc)})"
    )


def render_quarantine_insert_sql(
    record: QuarantineEvidenceRecord, *, catalog: str = "main", schema: str = "ops"
) -> str:
    table = evidence_table_names(catalog, schema)["quarantine"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, record_ref, reason, quarantined_at_utc) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_s(record.record_ref)}, {_s(record.reason)}, "
        f"{_ts(record.quarantined_at_utc)})"
    )


def render_source_metadata_insert_sql(
    record: SourceMetadataEvidenceRecord, *, catalog: str = "main", schema: str = "ops"
) -> str:
    table = evidence_table_names(catalog, schema)["metadata"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, source_metadata_json, captured_at_utc) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_json(record.source_metadata)}, "
        f"{_ts(record.captured_at_utc)})"
    )


def render_stream_batch_insert_sql(
    record: StreamBatchEvidenceRecord, *, catalog: str = "main", schema: str = "ops"
) -> str:
    table = evidence_table_names(catalog, schema)["streams"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, batch_id, batch_metrics_json, captured_at_utc) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_s(record.batch_id)}, {_json(record.batch_metrics)}, "
        f"{_ts(record.captured_at_utc)})"
    )


def render_access_insert_sql(record: AccessEvidenceRecord, *, catalog: str = "main", schema: str = "ops") -> str:
    table = evidence_table_names(catalog, schema)["access"]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, action, status, payload_json, applied_at_utc) VALUES "
        f"({_s(record.run_id)}, {_s(record.target_table)}, {_s(record.action)}, {_s(record.status)}, "
        f"{_json(record.payload)}, {_ts(record.applied_at_utc)})"
    )


def _json(value: dict[str, Any]) -> str:
    return _s(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _s(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _ts(value: datetime | None) -> str:
    if value is None:
        return "NULL"
    return f"TIMESTAMP {_s(value.strftime('%Y-%m-%d %H:%M:%S'))}"
