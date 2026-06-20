"""BigQuery operational cost SQL rendering."""

from __future__ import annotations

from collections.abc import Iterable

from contractforge_gcp.cost.model import CostModel
from contractforge_gcp.rendering.names import table_prefix

VALID_COST_GROUP_FIELDS = {
    "adapter",
    "contract_name",
    "statement_type",
    "status",
    "target_table",
}
DEFAULT_COST_GROUP_BY = ("target_table", "status", "statement_type")
_BYTES_PER_TIB = 1024**4


def render_operational_cost_query(
    *,
    project_id: str | None = None,
    dataset: str = "contractforge_ops",
    lookback_days: int = 30,
    group_by: Iterable[str] | None = None,
    cost_model: CostModel | None = None,
    include_failed: bool = True,
) -> str:
    if lookback_days < 1:
        raise ValueError("lookback_days must be greater than or equal to 1")
    fields = _normalize_group_by(group_by)
    model = cost_model or CostModel()
    _validate_float("bytes_processed_per_tib_rate", model.bytes_processed_per_tib_rate)
    _validate_float("slot_hour_rate", model.slot_hour_rate)
    table = f"`{table_prefix(project_id, dataset)}.contractforge_run_evidence`"
    status_filter = "" if include_failed else "AND status = 'SUCCEEDED'"
    bytes_rate = (
        "NULL"
        if model.bytes_processed_per_tib_rate is None
        else repr(float(model.bytes_processed_per_tib_rate))
    )
    slot_rate = "NULL" if model.slot_hour_rate is None else repr(float(model.slot_hour_rate))
    return f"""
WITH base AS (
  SELECT
    target_table,
    contract_name,
    adapter,
    status,
    COALESCE(statement_type, 'UNKNOWN') AS statement_type,
    COALESCE(total_bytes_processed, 0) AS total_bytes_processed,
    COALESCE(total_bytes_billed, 0) AS total_bytes_billed,
    COALESCE(total_slot_ms, 0) AS total_slot_ms,
    COALESCE(inserted_rows, 0) AS inserted_rows,
    COALESCE(updated_rows, 0) AS updated_rows,
    COALESCE(deleted_rows, 0) AS deleted_rows
  FROM {table}
  WHERE COALESCE(finished_at, started_at, CURRENT_TIMESTAMP())
    >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {int(lookback_days)} DAY)
    {status_filter}
),
agg AS (
  SELECT
    {_group_select(fields)},
    COUNT(*) AS runs,
    SUM(CASE WHEN status = 'SUCCEEDED' THEN 1 ELSE 0 END) AS successful_runs,
    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_runs,
    SUM(total_bytes_processed) AS total_bytes_processed,
    SUM(total_bytes_billed) AS total_bytes_billed,
    SUM(total_slot_ms) AS total_slot_ms,
    SUM(inserted_rows) AS inserted_rows,
    SUM(updated_rows) AS updated_rows,
    SUM(deleted_rows) AS deleted_rows
  FROM base
  GROUP BY {_group_by(fields)}
)
SELECT
  *,
  {bytes_rate} AS bytes_processed_per_tib_rate,
  {slot_rate} AS slot_hour_rate,
  '{_sql_string(model.currency)}' AS estimated_currency,
  CASE
    WHEN {bytes_rate} IS NULL THEN NULL
    ELSE total_bytes_processed / {_BYTES_PER_TIB}.0 * {bytes_rate}
  END AS estimated_bytes_processed_cost,
  CASE
    WHEN {slot_rate} IS NULL THEN NULL
    ELSE total_slot_ms / 3600000.0 * {slot_rate}
  END AS estimated_slot_cost,
  CASE
    WHEN {bytes_rate} IS NULL AND {slot_rate} IS NULL THEN NULL
    ELSE COALESCE(total_bytes_processed / {_BYTES_PER_TIB}.0 * {bytes_rate}, 0)
       + COALESCE(total_slot_ms / 3600000.0 * {slot_rate}, 0)
  END AS estimated_total_cost,
  'estimated_from_bigquery_job_evidence' AS cost_source
FROM agg
ORDER BY estimated_total_cost DESC NULLS LAST, total_slot_ms DESC, total_bytes_processed DESC
""".strip()


def _normalize_group_by(group_by: Iterable[str] | None) -> tuple[str, ...]:
    fields = tuple(group_by or DEFAULT_COST_GROUP_BY)
    if not fields:
        raise ValueError("group_by must contain at least one field")
    unknown = sorted(set(fields) - VALID_COST_GROUP_FIELDS)
    if unknown:
        raise ValueError(f"unknown group_by fields: {unknown}")
    return fields


def _validate_float(name: str, value: float | None) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{name} must be greater than or equal to 0")


def _group_select(fields: tuple[str, ...]) -> str:
    return ",\n    ".join(_identifier(field) for field in fields)


def _group_by(fields: tuple[str, ...]) -> str:
    return ", ".join(_identifier(field) for field in fields)


def _identifier(value: str) -> str:
    return f"`{value.replace('`', '')}`"


def _sql_string(value: str) -> str:
    return str(value).replace("'", "\\'")
