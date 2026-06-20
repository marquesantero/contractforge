"""Governance and operations control-table SQL rendering."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.config import CTRL_SCHEMA_VERSION, FRAMEWORK_VERSION
from contractforge_databricks.evidence.helpers import TimestampClock, cast_sql, utc_timestamp
from contractforge_databricks.evidence.schemas import EVIDENCE_TABLE_COLUMNS
from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.security import redact_text, redact_value
from contractforge_databricks.sql import quote_table_name, sql_int, sql_string

ANNOTATION_COLUMNS = tuple(column.split(" ", 1)[0] for column in EVIDENCE_TABLE_COLUMNS["annotations"])
ACCESS_COLUMNS = tuple(column.split(" ", 1)[0] for column in EVIDENCE_TABLE_COLUMNS["access"])
OPERATION_COLUMNS = tuple(column.split(" ", 1)[0] for column in EVIDENCE_TABLE_COLUMNS["operations"])
INT_COLUMNS = {"ctrl_schema_version", "freshness_sla_minutes"}
BOOL_COLUMNS = {"revoke_unmanaged", "alert_on_failure", "alert_on_quality_fail"}
DATE_COLUMNS = {"annotation_date", "access_date"}
TIMESTAMP_COLUMNS = {"annotation_ts_utc", "access_ts_utc", "applied_at_utc", "recorded_at_utc"}


def render_annotation_log_insert_sql(
    payload: dict[str, Any],
    *,
    catalog: str = "main",
    schema: str = "ops",
    clock: TimestampClock | None = None,
) -> str:
    table = evidence_table_names(catalog, schema)["annotations"]
    enriched = _annotation_payload(payload, clock=clock)
    values = [_value(column, _alias(enriched, column)) for column in ANNOTATION_COLUMNS]
    return f"INSERT INTO {quote_table_name(table)} ({', '.join(ANNOTATION_COLUMNS)}) VALUES ({', '.join(values)})"


def render_annotation_log_insert_sqls(
    *,
    run_id: str,
    target_table: str,
    entries: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    catalog: str = "main",
    schema: str = "ops",
    clock: TimestampClock | None = None,
) -> tuple[str, ...]:
    return tuple(
        render_annotation_log_insert_sql(
            _annotation_payload({**entry, "run_id": run_id, "target_table": target_table}, clock=clock),
            catalog=catalog,
            schema=schema,
            clock=clock,
        )
        for entry in entries
    )


def render_access_log_insert_sql(
    payload: dict[str, Any],
    *,
    catalog: str = "main",
    schema: str = "ops",
    clock: TimestampClock | None = None,
) -> str:
    table = evidence_table_names(catalog, schema)["access"]
    enriched = _access_payload(payload, clock=clock)
    values = [_value(column, _alias(enriched, column)) for column in ACCESS_COLUMNS]
    return f"INSERT INTO {quote_table_name(table)} ({', '.join(ACCESS_COLUMNS)}) VALUES ({', '.join(values)})"


def render_access_log_insert_sqls(
    *,
    run_id: str,
    target_table: str,
    entries: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    catalog: str = "main",
    schema: str = "ops",
    clock: TimestampClock | None = None,
) -> tuple[str, ...]:
    return tuple(
        render_access_log_insert_sql(
            _access_payload(
                {**entry, "access_run_id": entry.get("access_run_id") or run_id, "run_id": run_id, "target_table": target_table},
                clock=clock,
            ),
            catalog=catalog,
            schema=schema,
            clock=clock,
        )
        for entry in entries
    )


def render_operations_log_insert_sql(
    payload: dict[str, Any],
    *,
    catalog: str = "main",
    schema: str = "ops",
    clock: TimestampClock | None = None,
) -> str:
    table = evidence_table_names(catalog, schema)["operations"]
    enriched = _operations_payload(payload, clock=clock)
    values = [_value(column, enriched.get(column)) for column in OPERATION_COLUMNS]
    return f"INSERT INTO {quote_table_name(table)} ({', '.join(OPERATION_COLUMNS)}) VALUES ({', '.join(values)})"


def _annotation_payload(payload: dict[str, Any], *, clock: TimestampClock | None = None) -> dict[str, Any]:
    now = _utc_timestamp(clock)
    return {
        **payload,
        "applied_sql": payload.get("applied_sql", payload.get("sql")),
        "annotation_ts_utc": payload.get("annotation_ts_utc") or now,
        "annotation_date": payload.get("annotation_date") or now[:10],
        "framework_version": payload.get("framework_version") or FRAMEWORK_VERSION,
        "ctrl_schema_version": payload.get("ctrl_schema_version") or CTRL_SCHEMA_VERSION,
    }


def _access_payload(payload: dict[str, Any], *, clock: TimestampClock | None = None) -> dict[str, Any]:
    now = _utc_timestamp(clock)
    enriched = {
        **payload,
        "applied_sql": payload.get("applied_sql", payload.get("sql")),
        "action": payload.get("action") or payload.get("access_type"),
        "access_ts_utc": payload.get("access_ts_utc") or now,
        "access_date": payload.get("access_date") or now[:10],
        "applied_at_utc": payload.get("applied_at_utc") or now,
        "framework_version": payload.get("framework_version") or FRAMEWORK_VERSION,
        "ctrl_schema_version": payload.get("ctrl_schema_version") or CTRL_SCHEMA_VERSION,
    }
    return {**enriched, "payload_json": payload.get("payload_json", enriched)}


def _operations_payload(payload: dict[str, Any], *, clock: TimestampClock | None = None) -> dict[str, Any]:
    return {
        **payload,
        "recorded_at_utc": payload.get("recorded_at_utc") or _utc_timestamp(clock),
        "framework_version": payload.get("framework_version") or FRAMEWORK_VERSION,
        "ctrl_schema_version": payload.get("ctrl_schema_version") or CTRL_SCHEMA_VERSION,
    }


def _alias(payload: dict[str, Any], column: str) -> Any:
    if column == "applied_sql":
        return payload.get("applied_sql", payload.get("sql"))
    if column == "payload_json" and "payload_json" not in payload:
        return payload
    return payload.get(column)


def _value(column: str, value: Any) -> str:
    if column in INT_COLUMNS:
        return sql_int(value)
    if column in BOOL_COLUMNS:
        return "NULL" if value is None else str(bool(value)).lower()
    if column in DATE_COLUMNS:
        return cast_sql(value, "DATE")
    if column in TIMESTAMP_COLUMNS or column.endswith("_utc"):
        return cast_sql(value, "TIMESTAMP")
    if column.endswith("_json"):
        return sql_string(_json_text(value))
    if column == "error_message":
        return sql_string(redact_text(str(value))[:2000] if value is not None else None)
    return sql_string(redact_value(value))


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return redact_text(value)
    return json.dumps(redact_value(value), sort_keys=True, separators=(",", ":"))


def _utc_timestamp(clock: TimestampClock | None = None) -> str:
    return utc_timestamp(clock)
