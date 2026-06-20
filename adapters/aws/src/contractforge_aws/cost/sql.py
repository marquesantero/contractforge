"""AWS Glue operational cost SQL rendering."""

from __future__ import annotations

from collections.abc import Iterable

from contractforge_aws.cost.model import CostModel
from contractforge_aws.evidence import evidence_table_names

VALID_COST_GROUP_FIELDS = {
    "contract_domain",
    "contract_owner",
    "layer",
    "target_table",
    "mode",
    "runtime_type",
    "source_connector",
    "source_provider",
    "status",
}
DEFAULT_COST_GROUP_BY = ("target_table", "layer", "mode", "status")


def render_operational_cost_query(
    *,
    database: str = "contractforge_ops",
    lookback_days: int = 30,
    group_by: Iterable[str] | None = None,
    cost_model: CostModel | None = None,
    include_failed: bool = True,
) -> str:
    if lookback_days < 1:
        raise ValueError("lookback_days must be greater than or equal to 1")
    fields = _normalize_group_by(group_by)
    model = cost_model or CostModel()
    _validate_float("dpu_hour_usd", model.dpu_hour_usd)
    tables = evidence_table_names(database)
    status_filter = "" if include_failed else "AND runs.status = 'SUCCESS'"
    hourly_rate = "NULL" if model.hourly_rate is None else repr(float(model.hourly_rate))
    return f"""
WITH cost_by_run AS (
    SELECT
        run_id,
        target_table,
        SUM(CASE WHEN signal_name = 'glue_dpu_seconds' THEN signal_value ELSE 0.0 END) AS dpu_seconds
    FROM {tables["cost"]}
    GROUP BY run_id, target_table
),
base AS (
    SELECT
        runs.target_table,
        runs.layer,
        runs.mode,
        runs.status,
        runs.contract_domain,
        runs.contract_owner,
        runs.runtime_type,
        runs.source_connector,
        runs.source_provider,
        CAST(COALESCE(runs.rows_read, 0) AS BIGINT) AS rows_read,
        CAST(COALESCE(runs.rows_written, 0) AS BIGINT) AS rows_written,
        CAST(COALESCE(runs.rows_quarantined, 0) AS BIGINT) AS rows_quarantined,
        CAST(COALESCE(runs.duration_seconds, 0.0) AS DOUBLE) AS duration_seconds,
        CAST(COALESCE(cost_by_run.dpu_seconds, 0.0) AS DOUBLE) AS dpu_seconds
    FROM {tables["runs"]} runs
    LEFT JOIN cost_by_run
      ON runs.run_id = cost_by_run.run_id
     AND runs.target_table = cost_by_run.target_table
    WHERE runs.run_date >= date_sub(current_date(), {int(lookback_days)})
      {status_filter}
),
agg AS (
    SELECT
        {_group_select(fields)},
        COUNT(*) AS runs,
        SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successful_runs,
        SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_runs,
        SUM(rows_read) AS rows_read,
        SUM(rows_written) AS rows_written,
        SUM(rows_quarantined) AS rows_quarantined,
        SUM(duration_seconds) AS duration_seconds,
        SUM(dpu_seconds) AS dpu_seconds
    FROM base
    GROUP BY {_group_by(fields)}
)
SELECT
    *,
    CASE WHEN duration_seconds > 0 THEN rows_written / duration_seconds ELSE NULL END AS rows_written_per_second,
    CASE WHEN duration_seconds > 0 THEN rows_read / duration_seconds ELSE NULL END AS rows_read_per_second,
    CASE WHEN runs > 0 THEN duration_seconds / runs ELSE NULL END AS avg_duration_seconds,
    {hourly_rate} AS estimated_dpu_hour_usd,
    {_string(model.currency)} AS estimated_currency,
    CASE WHEN {hourly_rate} IS NULL THEN NULL ELSE dpu_seconds / 3600.0 * {hourly_rate} END AS estimated_compute_cost,
    CASE
        WHEN {hourly_rate} IS NULL OR rows_written <= 0 THEN NULL
        ELSE (dpu_seconds / 3600.0 * {hourly_rate}) / (rows_written / 1000000.0)
    END AS estimated_cost_per_million_rows,
    'estimated_from_glue_dpu_seconds' AS cost_source
FROM agg
ORDER BY estimated_compute_cost DESC NULLS LAST, dpu_seconds DESC, duration_seconds DESC
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
    return ",\n        ".join(_quote_identifier(field) for field in fields)


def _group_by(fields: tuple[str, ...]) -> str:
    return ", ".join(_quote_identifier(field) for field in fields)


def _quote_identifier(value: str) -> str:
    return f"`{str(value).replace('`', '``')}`"


def _string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"
