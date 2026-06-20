"""Render AWS Glue run-evidence context setup."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.database import evidence_database
from contractforge_aws.evidence.ddl import render_evidence_table_ddl, render_runs_table_ddl
from contractforge_aws.rendering.names import iceberg_table_name


def render_evidence_context(
    contract: SemanticContract,
    *,
    dataframe_name: str = "df",
    rows_read_expression: str | None = None,
    evidence_database_name: str | None = None,
) -> str:
    database = evidence_database(contract, evidence_database_name)
    target_table = iceberg_table_name(contract)
    snapshot_query = f"SELECT snapshot_id, summary FROM {target_table}.snapshots ORDER BY committed_at DESC LIMIT 1"
    return "\n".join(
        [
            "# Prepare run metrics shared by state, metadata and final run evidence.",
            f"spark.sql('CREATE DATABASE IF NOT EXISTS glue_catalog.`{database}`')",
            f"spark.sql('''{render_runs_table_ddl(database)}''')",
            f"spark.sql('''{render_evidence_table_ddl('errors', database)}''')",
            f"spark.sql('''{render_evidence_table_ddl('cost', database)}''')",
            "_cf_snapshots = []",
            "if not globals().get('_cf_no_input_skip', False):",
            "    try:",
            f"        _cf_snapshots = spark.sql({snapshot_query!r}).collect()",
            "    except Exception:",
            "        _cf_snapshots = []",
            "if globals().get('_cf_no_input_skip', False) or globals().get('_cf_skip_reason') == 'no_hash_changes':",
            "    _cf_summary = {'skip_reason': globals().get('_cf_skip_reason', 'no_new_input')}",
            "else:",
            "    _cf_summary = {str(k): str(v) for k, v in dict(_cf_snapshots[0]['summary']).items()} if _cf_snapshots else {}",
            "_cf_hash_diff_metrics = {",
            "    'hash_diff_candidate_rows': globals().get('_cf_hash_diff_candidate_rows'),",
            "    'hash_input_columns': globals().get('_cf_hash_input_columns'),",
            "}",
            "for _cf_metric_name, _cf_metric_value in _cf_hash_diff_metrics.items():",
            "    if _cf_metric_value is not None:",
            "        _cf_summary[_cf_metric_name] = _cf_metric_value",
            f"_cf_rows_read = {rows_read_expression or f'int({dataframe_name}.count())'}",
            "_cf_finished_at = datetime.now(timezone.utc)",
            "_cf_duration = (_cf_finished_at - _cf_run_now).total_seconds()",
            "_cf_spark_version = spark.version",
            "_cf_python_version = sys.version.split()[0]",
        ]
    )
