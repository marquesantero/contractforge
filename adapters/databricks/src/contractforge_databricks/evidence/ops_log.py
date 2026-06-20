"""Operational control-table SQL rendering."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.config import CTRL_SCHEMA_VERSION, FRAMEWORK_VERSION
from contractforge_databricks.evidence.helpers import TimestampClock, cast_sql, utc_timestamp
from contractforge_databricks.evidence.schemas import EVIDENCE_TABLE_COLUMNS
from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.security import redact_text, redact_value
from contractforge_databricks.sql import quote_identifier, quote_table_name, sql_int, sql_string

ERROR_COLUMNS = tuple(column.split(" ", 1)[0] for column in EVIDENCE_TABLE_COLUMNS["errors"])
SCHEMA_CHANGE_COLUMNS = tuple(column.split(" ", 1)[0] for column in EVIDENCE_TABLE_COLUMNS["schema_changes"])
STREAM_COLUMNS = tuple(column.split(" ", 1)[0] for column in EVIDENCE_TABLE_COLUMNS["streams"])
INT_COLUMNS = {
    "ctrl_schema_version",
    "batches_processed",
    "total_rows_read",
    "total_rows_written",
    "total_rows_quarantined",
}
FLOAT_COLUMNS = {"duration_seconds"}
BOOL_COLUMNS = {"applied"}
DATE_COLUMNS = {"error_date", "access_date", "annotation_date"}
TIMESTAMP_COLUMNS = {
    "error_ts_utc",
    "occurred_at_utc",
    "change_ts_utc",
    "changed_at_utc",
    "started_at_utc",
    "ended_at_utc",
    "captured_at_utc",
}


def render_error_log_insert_sql(
    payload: dict[str, Any],
    *,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    table = evidence_table_names(catalog, schema)["errors"]
    values = [_value(column, payload.get(column)) for column in ERROR_COLUMNS]
    return f"INSERT INTO {quote_table_name(table)} ({', '.join(ERROR_COLUMNS)}) VALUES ({', '.join(values)})"


def render_schema_change_log_insert_sql(
    payload: dict[str, Any],
    *,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    table = evidence_table_names(catalog, schema)["schema_changes"]
    values = [_value(column, payload.get(column)) for column in SCHEMA_CHANGE_COLUMNS]
    return (
        f"INSERT INTO {quote_table_name(table)} ({', '.join(SCHEMA_CHANGE_COLUMNS)}) VALUES "
        f"({', '.join(values)})"
    )


def render_schema_change_log_insert_sqls(
    *,
    run_id: str,
    target_table: str,
    schema_changes: dict[str, Any],
    source_schema: dict[str, str] | None = None,
    catalog: str = "main",
    schema: str = "ops",
    clock: TimestampClock | None = None,
) -> tuple[str, ...]:
    now = _utc_timestamp(clock)
    rows = []
    for column in schema_changes.get("added_columns") or ():
        source_type = (source_schema or {}).get(column)
        payload = {"column": column, "source_type": source_type}
        rows.append(
            {
                "run_id": run_id,
                "change_ts_utc": now,
                "target_table": target_table,
                "change_type": "add_column",
                "column_name": column,
                "source_type": source_type,
                "applied": True,
                "details_json": {},
                "payload_json": payload,
                "changed_at_utc": now,
                "framework_version": FRAMEWORK_VERSION,
                "ctrl_schema_version": CTRL_SCHEMA_VERSION,
            }
        )
    for change in schema_changes.get("type_changes") or ():
        rows.append(
            {
                "run_id": run_id,
                "change_ts_utc": now,
                "target_table": target_table,
                "change_type": change.get("change", "type_change"),
                "column_name": change.get("column"),
                "source_type": change.get("source"),
                "target_type": change.get("target"),
                "applied": bool(change.get("applied")),
                "details_json": change,
                "payload_json": change,
                "changed_at_utc": now,
                "framework_version": FRAMEWORK_VERSION,
                "ctrl_schema_version": CTRL_SCHEMA_VERSION,
            }
        )
    return tuple(render_schema_change_log_insert_sql(row, catalog=catalog, schema=schema) for row in rows)


def render_stream_log_insert_sql(
    payload: dict[str, Any],
    *,
    catalog: str = "main",
    schema: str = "ops",
    clock: TimestampClock | None = None,
) -> str:
    table = evidence_table_names(catalog, schema)["streams"]
    enriched = _stream_start_payload(payload, clock=clock)
    values = [_value(column, enriched.get(column)) for column in STREAM_COLUMNS]
    return f"INSERT INTO {quote_table_name(table)} ({', '.join(STREAM_COLUMNS)}) VALUES ({', '.join(values)})"


def render_stream_finish_update_sql(
    *,
    stream_run_id: str,
    payload: dict[str, Any],
    catalog: str = "main",
    schema: str = "ops",
) -> str | None:
    assignments = [
        f"{quote_identifier(column)} = {_value(column, payload[column])}"
        for column in STREAM_COLUMNS
        if column != "stream_run_id" and column in payload
    ]
    if not assignments:
        return None
    table = evidence_table_names(catalog, schema)["streams"]
    return (
        f"UPDATE {quote_table_name(table)} SET {', '.join(assignments)} "
        f"WHERE stream_run_id = {sql_string(stream_run_id)}"
    )


def render_stream_child_run_metrics_sql(
    *,
    stream_run_id: str,
    runs_table: str = "main.ops.ctrl_ingestion_runs",
) -> str:
    return "\n".join(
        [
            "SELECT",
            "  count(1) AS batches_processed,",
            "  sum(coalesce(rows_read, 0)) AS total_rows_read,",
            "  sum(coalesce(rows_written, 0)) AS total_rows_written,",
            "  sum(coalesce(rows_quarantined, 0)) AS total_rows_quarantined",
            f"FROM {quote_table_name(runs_table)}",
            f"WHERE parent_run_id = {sql_string(stream_run_id)}",
        ]
    )


def _value(column: str, value: Any) -> str:
    if column in INT_COLUMNS:
        return sql_int(value)
    if column in FLOAT_COLUMNS:
        return "NULL" if value is None else str(float(value))
    if column in BOOL_COLUMNS:
        return "NULL" if value is None else str(bool(value)).lower()
    if column in DATE_COLUMNS:
        return cast_sql(value, "DATE")
    if column in TIMESTAMP_COLUMNS or column.endswith("_utc"):
        return cast_sql(value, "TIMESTAMP")
    if column.endswith("_json"):
        return sql_string(_json_text(value))
    if column in {"error_message", "stack_trace"}:
        return sql_string(redact_text(str(value))[:4000] if value is not None else None)
    return sql_string(redact_value(value))


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return redact_text(value)
    return json.dumps(redact_value(value), sort_keys=True, separators=(",", ":"))


def _stream_start_payload(payload: dict[str, Any], *, clock: TimestampClock | None = None) -> dict[str, Any]:
    now = _utc_timestamp(clock)
    return {
        **payload,
        "started_at_utc": payload.get("started_at_utc") or now,
        "captured_at_utc": payload.get("captured_at_utc") or now,
        "batches_processed": payload.get("batches_processed", 0),
        "total_rows_read": payload.get("total_rows_read", 0),
        "total_rows_written": payload.get("total_rows_written", 0),
        "total_rows_quarantined": payload.get("total_rows_quarantined", 0),
        "framework_version": payload.get("framework_version") or FRAMEWORK_VERSION,
        "ctrl_schema_version": payload.get("ctrl_schema_version") or CTRL_SCHEMA_VERSION,
    }


def _utc_timestamp(clock: TimestampClock | None = None) -> str:
    return utc_timestamp(clock)
