"""Databricks SQL for locks, state and idempotency lookups."""

from __future__ import annotations

from contractforge_databricks.sql import quote_table_name, sql_int, sql_string
from contractforge_databricks.state.tables import state_table_names


def render_acquire_lock_sql(
    *,
    target_table: str,
    run_id: str,
    owner: str | None = None,
    ttl_minutes: int = 60,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    table = state_table_names(catalog, schema)["locks"]
    return f"""
MERGE INTO {quote_table_name(table)} t
USING (
  SELECT
    {sql_string(target_table)} AS target_table,
    {sql_string(run_id)} AS run_id,
    {sql_string(owner)} AS owner,
    current_timestamp() AS acquired_at_utc,
    current_timestamp() + INTERVAL {int(ttl_minutes)} MINUTES AS expires_at_utc,
    {sql_int(ttl_minutes)} AS ttl_minutes,
    CAST(NULL AS TIMESTAMP) AS released_at_utc,
    'ACTIVE' AS status
) s
ON t.target_table = s.target_table
WHEN MATCHED AND (t.status <> 'ACTIVE' OR t.expires_at_utc < current_timestamp()) THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
""".strip()


def render_release_lock_sql(
    *, target_table: str, run_id: str, catalog: str = "main", schema: str = "ops"
) -> str:
    table = state_table_names(catalog, schema)["locks"]
    return f"""
UPDATE {quote_table_name(table)}
SET status = 'RELEASED',
    released_at_utc = current_timestamp()
WHERE target_table = {sql_string(target_table)} AND run_id = {sql_string(run_id)}
""".strip()


def render_upsert_state_sql(
    *,
    target_table: str,
    run_id: str,
    status: str,
    rows_written: int,
    watermark_column: str | None = None,
    watermark_value: str | None = None,
    success_at_utc: str | None = None,
    error_message: str | None = None,
    table_version: str | None = None,
    write_completed_at_utc: str | None = None,
    watermark_candidate: str | None = None,
    parent_run_id: str | None = None,
    run_group_id: str | None = None,
    master_job_id: str | None = None,
    master_run_id: str | None = None,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    table = state_table_names(catalog, schema)["state"]
    return f"""
MERGE INTO {quote_table_name(table)} t
USING (
  SELECT
    {sql_string(target_table)} AS target_table,
    {sql_string(watermark_column)} AS watermark_column,
    {sql_string(watermark_value)} AS watermark_value,
    CAST({sql_string(success_at_utc)} AS TIMESTAMP) AS last_success_at_utc,
    {sql_string(run_id)} AS last_run_id,
    {sql_string(status)} AS last_status,
    {sql_int(rows_written)} AS last_rows_written,
    {sql_string(_truncate(error_message))} AS last_error_message,
    {sql_string(parent_run_id)} AS parent_run_id,
    {sql_string(run_group_id)} AS run_group_id,
    {sql_string(master_job_id)} AS master_job_id,
    {sql_string(master_run_id)} AS master_run_id,
    {sql_string(table_version)} AS last_table_version,
    CAST({sql_string(write_completed_at_utc)} AS TIMESTAMP) AS last_write_completed_at_utc,
    {sql_string(watermark_candidate)} AS last_watermark_candidate,
    current_timestamp() AS last_updated_at_utc
) s
ON t.target_table = s.target_table
WHEN MATCHED THEN UPDATE SET
  t.watermark_column = s.watermark_column,
  t.watermark_value = s.watermark_value,
  t.last_success_at_utc = s.last_success_at_utc,
  t.last_run_id = s.last_run_id,
  t.last_status = s.last_status,
  t.last_rows_written = s.last_rows_written,
  t.last_error_message = s.last_error_message,
  t.parent_run_id = s.parent_run_id,
  t.run_group_id = s.run_group_id,
  t.master_job_id = s.master_job_id,
  t.master_run_id = s.master_run_id,
  t.last_table_version = s.last_table_version,
  t.last_write_completed_at_utc = s.last_write_completed_at_utc,
  t.last_watermark_candidate = s.last_watermark_candidate,
  t.last_updated_at_utc = s.last_updated_at_utc
WHEN NOT MATCHED THEN INSERT *
""".strip()


def _truncate(value: str | None, limit: int = 4000) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return value[:limit]
