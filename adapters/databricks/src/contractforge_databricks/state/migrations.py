"""Additive Databricks control-table migration planning."""

from __future__ import annotations

from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.sql import quote_identifier, quote_table_name
from contractforge_databricks.state.tables import state_table_names


EVIDENCE_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "runs": {
        "idempotency_key": "STRING",
        "idempotency_policy": "STRING",
        "skip_reason": "STRING",
        "skipped_by_run_id": "STRING",
        "metrics_source": "STRING",
        "framework_version": "STRING",
        "ctrl_schema_version": "BIGINT",
        "runtime_type": "STRING",
        "engine_version": "STRING",
        "python_version": "STRING",
        "stage_durations_json": "STRING",
        "contract_description": "STRING",
        "contract_owner": "STRING",
        "contract_domain": "STRING",
        "contract_tags_json": "STRING",
        "contract_sla": "STRING",
        "runtime_parameters_json": "STRING",
        "annotations_status": "STRING",
        "annotations_result_json": "STRING",
        "ownership_json": "STRING",
        "operations_json": "STRING",
        "source_type": "STRING",
        "source_connector": "STRING",
        "source_name": "STRING",
        "source_provider": "STRING",
        "source_format": "STRING",
        "source_path": "STRING",
        "source_options_json": "STRING",
        "source_read_json": "STRING",
        "source_request_json": "STRING",
        "source_auth_json": "STRING",
        "source_pagination_json": "STRING",
        "source_response_json": "STRING",
        "source_incremental_json": "STRING",
        "source_limits_json": "STRING",
        "source_capabilities_json": "STRING",
        "source_metrics_json": "STRING",
        "source_system": "STRING",
        "write_engine_requested": "STRING",
        "write_engine_selected": "STRING",
        "write_engine_status": "STRING",
        "write_engine_reason": "STRING",
        "write_engine_fallback_policy": "STRING",
        "write_started_at_utc": "TIMESTAMP",
        "write_finished_at_utc": "TIMESTAMP",
        "table_version_before": "STRING",
        "table_version_after": "STRING",
        "write_committed": "BOOLEAN",
        "parent_run_id": "STRING",
        "run_group_id": "STRING",
        "master_job_id": "STRING",
        "master_run_id": "STRING",
        "rows_expired": "BIGINT",
        "metrics_json": "STRING",
    },
    "errors": {"error_class": "STRING", "occurred_at_utc": "TIMESTAMP"},
    "quality": {"severity": "STRING", "observed_value": "STRING", "message": "STRING"},
    "quarantine": {"record_ref": "STRING", "reason": "STRING"},
    "schema_changes": {"payload_json": "STRING", "changed_at_utc": "TIMESTAMP"},
    "lineage": {"source_name": "STRING"},
    "metadata": {
        "run_id": "STRING",
        "target_table": "STRING",
        "source_metadata_json": "STRING",
        "captured_at_utc": "TIMESTAMP",
    },
    "streams": {
        "run_id": "STRING",
        "batch_id": "STRING",
        "batch_metrics_json": "STRING",
        "captured_at_utc": "TIMESTAMP",
    },
    "annotations": {"previous_value": "STRING", "annotation_date": "DATE"},
    "operations": {"ownership_json": "STRING"},
    "access": {
        "access_run_id": "STRING",
        "action": "STRING",
        "column_name": "STRING",
        "function_name": "STRING",
        "new_value": "STRING",
        "mode": "STRING",
        "drift_policy": "STRING",
        "revoke_unmanaged": "BOOLEAN",
        "access_date": "DATE",
        "payload_json": "STRING",
        "applied_at_utc": "TIMESTAMP",
    },
}

STATE_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "state": {
        "parent_run_id": "STRING",
        "run_group_id": "STRING",
        "master_job_id": "STRING",
        "master_run_id": "STRING",
        "last_table_version": "STRING",
        "last_write_completed_at_utc": "TIMESTAMP",
        "last_watermark_candidate": "STRING",
    },
    "locks": {
        "owner": "STRING",
        "ttl_minutes": "BIGINT",
        "released_at_utc": "TIMESTAMP",
    },
}


def control_table_additive_migrations(*, catalog: str = "main", schema: str = "ops") -> dict[str, dict[str, str]]:
    tables = {**evidence_table_names(catalog, schema), **state_table_names(catalog, schema)}
    migrations: dict[str, dict[str, str]] = {}
    for key, columns in {**EVIDENCE_ADDITIVE_COLUMNS, **STATE_ADDITIVE_COLUMNS}.items():
        migrations[tables[key]] = dict(columns)
    return migrations


def render_control_table_migrations_sql(*, catalog: str = "main", schema: str = "ops") -> str:
    lines = [
        "-- Databricks control-table additive migrations.",
        "-- Review existing schemas before execution; apply only columns that are missing.",
        "",
    ]
    for table, columns in control_table_additive_migrations(catalog=catalog, schema=schema).items():
        rendered_columns = ",\n  ".join(
            f"{quote_identifier(column)} {column_type}" for column, column_type in columns.items()
        )
        lines.extend(
            [
                f"-- {table}",
                f"ALTER TABLE {quote_table_name(table)} ADD COLUMNS (",
                f"  {rendered_columns}",
                ");",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
