"""AWS performance evidence SQL renderers."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.runtime import evidence_database
from contractforge_aws.rendering.names import iceberg_table_name


def render_performance_benchmark_query(
    contract: SemanticContract,
    *,
    evidence_database_name: str | None = None,
) -> str:
    """Render an Athena-compatible benchmark report query for one target."""

    database = _quote_identifier(evidence_database(contract, evidence_database_name))
    target = _literal(iceberg_table_name(contract))
    return "\n".join(
        [
            "-- ContractForge AWS benchmark evidence report.",
            "-- Run after representative initial_load, no_change_replay and changed_row_wave cases.",
            "WITH cost_by_run AS (",
            "  SELECT",
            "    run_id,",
            "    target_table,",
            "    sum(signal_value) AS glue_dpu_seconds,",
            "    max(payload_json) AS glue_jobrun_payload_json",
            f"  FROM {database}.\"ctrl_ingestion_cost\"",
            "  WHERE signal_name = 'glue_dpu_seconds'",
            "  GROUP BY run_id, target_table",
            "), ranked_runs AS (",
            "  SELECT",
            "    runs.run_id,",
            "    runs.run_ts_utc,",
            "    runs.target_table,",
            "    runs.mode,",
            "    runs.status,",
            "    runs.quality_status,",
            "    runs.skip_reason,",
            "    runs.rows_read,",
            "    runs.rows_written,",
            "    runs.rows_inserted,",
            "    runs.rows_updated,",
            "    runs.rows_deleted,",
            "    runs.rows_quarantined,",
            "    runs.duration_seconds,",
            "    runs.table_version_after,",
            "    runs.operation_metrics_json,",
            "    cost_by_run.glue_dpu_seconds,",
            "    cost_by_run.glue_jobrun_payload_json,",
            "    row_number() OVER (PARTITION BY runs.target_table ORDER BY runs.run_ts_utc ASC) AS target_run_number",
            f"  FROM {database}.\"ctrl_ingestion_runs\" runs",
            "  LEFT JOIN cost_by_run",
            "    ON runs.run_id = cost_by_run.run_id",
            "   AND runs.target_table = cost_by_run.target_table",
            f"  WHERE runs.target_table = {target}",
            f"    AND runs.mode = {_literal(contract.write.mode)}",
            "    AND runs.status IN ('SUCCESS', 'SKIPPED')",
            ")",
            "SELECT",
            "  CASE",
            "    WHEN skip_reason = 'no_new_input' THEN 'no_change_replay'",
            "    WHEN target_run_number = 1 THEN 'initial_load'",
            "    WHEN rows_updated = 0 AND rows_inserted = 0 AND rows_deleted = 0 THEN 'no_change_replay'",
            "    ELSE 'changed_row_wave'",
            "  END AS benchmark_case,",
            "  run_id,",
            "  run_ts_utc,",
            "  status,",
            "  quality_status,",
            "  rows_read,",
            "  rows_written,",
            "  rows_inserted,",
            "  rows_updated,",
            "  rows_deleted,",
            "  rows_quarantined,",
            "  duration_seconds,",
            "  glue_dpu_seconds,",
            "  table_version_after,",
            "  operation_metrics_json,",
            "  glue_jobrun_payload_json",
            "FROM ranked_runs",
            "ORDER BY run_ts_utc ASC;",
            "",
        ]
    )


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"
