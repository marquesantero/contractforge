"""Databricks SQL lookup queries for control state."""

from __future__ import annotations

from contractforge_databricks.sql import quote_table_name, sql_int, sql_string


def render_lock_status_sql(*, target_table: str, locks_table: str = "main.ops.ctrl_ingestion_locks") -> str:
    return "\n".join(
        [
            "SELECT run_id, owner, status, acquired_at_utc, expires_at_utc, ttl_minutes",
            f"FROM {quote_table_name(locks_table)}",
            f"WHERE target_table = {sql_string(target_table)}",
            "LIMIT 1",
        ]
    )


def render_find_idempotent_run_sql(
    *,
    target_table: str,
    idempotency_key: str,
    status: str | None = None,
    runs_table: str = "main.ops.ctrl_ingestion_runs",
) -> str:
    filters = [
        f"target_table = {sql_string(target_table)}",
        f"idempotency_key = {sql_string(idempotency_key)}",
    ]
    if status:
        filters.append(f"status = {sql_string(status)}")
    return "\n".join(
        [
            "SELECT run_id, status",
            f"FROM {quote_table_name(runs_table)}",
            f"WHERE {' AND '.join(filters)}",
            "ORDER BY run_ts_utc DESC NULLS LAST",
            "LIMIT 1",
        ]
    )


def render_find_idempotent_stream_sql(
    *,
    target_table: str,
    idempotency_key: str,
    status: str | None = None,
    streams_table: str = "main.ops.ctrl_ingestion_streams",
) -> str:
    filters = [
        f"target_table = {sql_string(target_table)}",
        f"idempotency_key = {sql_string(idempotency_key)}",
    ]
    if status:
        filters.append(f"status = {sql_string(status)}")
    return "\n".join(
        [
            "SELECT stream_run_id, status",
            f"FROM {quote_table_name(streams_table)}",
            f"WHERE {' AND '.join(filters)}",
            "ORDER BY started_at_utc DESC NULLS LAST",
            "LIMIT 1",
        ]
    )


def render_has_successful_run_sql(
    *,
    target_table: str,
    idempotency_key: str,
    runs_table: str = "main.ops.ctrl_ingestion_runs",
) -> str:
    return "\n".join(
        [
            "SELECT count(1) > 0 AS has_successful_run",
            f"FROM {quote_table_name(runs_table)}",
            "WHERE "
            f"target_table = {sql_string(target_table)} "
            f"AND idempotency_key = {sql_string(idempotency_key)} "
            "AND status = 'SUCCESS'",
        ]
    )


def render_select_previous_watermark_sql(
    *,
    target_table: str,
    state_table: str = "main.ops.ctrl_ingestion_state",
) -> str:
    return "\n".join(
        [
            "SELECT watermark_value",
            f"FROM {quote_table_name(state_table)}",
            f"WHERE target_table = {sql_string(target_table)}",
            "LIMIT 1",
        ]
    )


def render_control_metadata_current_sql(
    *,
    framework_version: str,
    ctrl_schema_version: int,
    metadata_table: str = "main.ops.ctrl_ingestion_metadata",
) -> str:
    return "\n".join(
        [
            "SELECT 1",
            f"FROM {quote_table_name(metadata_table)}",
            "WHERE component = 'contractforge'",
            f"  AND framework_version = {sql_string(framework_version)}",
            f"  AND ctrl_schema_version = {sql_int(ctrl_schema_version)}",
            "LIMIT 1",
        ]
    )


def render_record_control_metadata_sql(
    *,
    framework_version: str,
    ctrl_schema_version: int,
    metadata_table: str = "main.ops.ctrl_ingestion_metadata",
) -> str:
    return f"""
MERGE INTO {quote_table_name(metadata_table)} t
USING (
  SELECT
    'contractforge' AS component,
    {sql_string(framework_version)} AS framework_version,
    {sql_int(ctrl_schema_version)} AS ctrl_schema_version,
    current_timestamp() AS updated_at_utc
) s
ON t.component = s.component
WHEN MATCHED THEN UPDATE SET
  t.framework_version = s.framework_version,
  t.ctrl_schema_version = s.ctrl_schema_version,
  t.updated_at_utc = s.updated_at_utc
WHEN NOT MATCHED THEN INSERT (
  component,
  framework_version,
  ctrl_schema_version,
  updated_at_utc
) VALUES (
  s.component,
  s.framework_version,
  s.ctrl_schema_version,
  s.updated_at_utc
)
""".strip()
