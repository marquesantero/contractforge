"""Databricks operational cost SQL rendering."""

from __future__ import annotations

from collections.abc import Iterable

from contractforge_databricks.cost.model import CostModel
from contractforge_databricks.evidence import evidence_table_names
from contractforge_databricks.sql import quote_identifier, quote_table_name, sql_string

VALID_COST_GROUP_FIELDS = {
    "contract_domain",
    "contract_owner",
    "criticality",
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
    catalog: str = "main",
    schema: str = "ops",
    lookback_days: int = 30,
    group_by: Iterable[str] | None = None,
    cost_model: CostModel | None = None,
    include_failed: bool = True,
) -> str:
    if lookback_days < 1:
        raise ValueError("lookback_days must be greater than or equal to 1")
    fields = _normalize_group_by(group_by)
    model = cost_model or CostModel()
    _validate_float("dbu_per_hour", model.dbu_per_hour)
    _validate_float("currency_per_dbu", model.currency_per_dbu)
    runs_table = evidence_table_names(catalog, schema)["runs"]
    status_filter = "" if include_failed else "AND status = 'SUCCESS'"
    hourly_rate = "NULL" if model.hourly_rate is None else repr(float(model.hourly_rate))
    return f"""
WITH base AS (
    SELECT
        target_table,
        layer,
        mode,
        status,
        contract_domain,
        contract_owner,
        runtime_type,
        source_connector,
        source_provider,
        COALESCE(
            get_json_object(operations_json, '$.metadata.criticality'),
            get_json_object(operations_json, '$.criticality'),
            'unknown'
        ) AS criticality,
        CAST(COALESCE(rows_read, 0) AS BIGINT) AS rows_read,
        CAST(COALESCE(rows_written, 0) AS BIGINT) AS rows_written,
        CAST(COALESCE(rows_quarantined, 0) AS BIGINT) AS rows_quarantined,
        CAST(COALESCE(duration_seconds, 0.0) AS DOUBLE) AS duration_seconds,
        CAST(COALESCE(get_json_object(stage_durations_json, '$.read'), '0') AS DOUBLE) AS read_seconds,
        CAST(COALESCE(get_json_object(stage_durations_json, '$.prepare'), '0') AS DOUBLE) AS prepare_seconds,
        CAST(COALESCE(get_json_object(stage_durations_json, '$.quality'), '0') AS DOUBLE) AS quality_seconds,
        CAST(COALESCE(get_json_object(stage_durations_json, '$.schema'), '0') AS DOUBLE) AS schema_seconds,
        CAST(COALESCE(get_json_object(stage_durations_json, '$.preflight'), '0') AS DOUBLE) AS preflight_seconds,
        CAST(COALESCE(get_json_object(stage_durations_json, '$.write'), '0') AS DOUBLE) AS write_seconds,
        CAST(COALESCE(get_json_object(stage_durations_json, '$.maintenance'), '0') AS DOUBLE) AS maintenance_seconds,
        CAST(COALESCE(get_json_object(stage_durations_json, '$.governance'), '0') AS DOUBLE) AS governance_seconds
    FROM {quote_table_name(runs_table)}
    WHERE run_date >= date_sub(current_date(), {int(lookback_days)})
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
        SUM(read_seconds) AS read_seconds,
        SUM(prepare_seconds) AS prepare_seconds,
        SUM(quality_seconds) AS quality_seconds,
        SUM(schema_seconds) AS schema_seconds,
        SUM(preflight_seconds) AS preflight_seconds,
        SUM(write_seconds) AS write_seconds,
        SUM(maintenance_seconds) AS maintenance_seconds,
        SUM(governance_seconds) AS governance_seconds
    FROM base
    GROUP BY {_group_by(fields)}
)
SELECT
    *,
    CASE WHEN duration_seconds > 0 THEN rows_written / duration_seconds ELSE NULL END AS rows_written_per_second,
    CASE WHEN duration_seconds > 0 THEN rows_read / duration_seconds ELSE NULL END AS rows_read_per_second,
    CASE WHEN runs > 0 THEN duration_seconds / runs ELSE NULL END AS avg_duration_seconds,
    {hourly_rate} AS estimated_hourly_rate,
    {sql_string(model.currency)} AS estimated_currency,
    CASE WHEN {hourly_rate} IS NULL THEN NULL ELSE duration_seconds / 3600.0 * {hourly_rate} END AS estimated_compute_cost,
    CASE
        WHEN {hourly_rate} IS NULL OR rows_written <= 0 THEN NULL
        ELSE (duration_seconds / 3600.0 * {hourly_rate}) / (rows_written / 1000000.0)
    END AS estimated_cost_per_million_rows,
    'estimated_from_evidence_runs' AS cost_source
FROM agg
ORDER BY estimated_compute_cost DESC NULLS LAST, duration_seconds DESC
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
    return ",\n        ".join(quote_identifier(field) for field in fields)


def _group_by(fields: tuple[str, ...]) -> str:
    return ", ".join(quote_identifier(field) for field in fields)
