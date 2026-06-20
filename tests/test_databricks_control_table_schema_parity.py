from contractforge_databricks.diagnostics import render_create_explain_table_sql
from contractforge_databricks.evidence import EVIDENCE_TABLE_COLUMNS
from contractforge_databricks.state.ddl import STATE_TABLE_SCHEMAS


CONTRACTFORGE_CONTROL_COLUMNS = {
    "runs": {
        "run_id",
        "run_ts_utc",
        "run_date",
        "runtime_entrypoint",
        "layer",
        "source_table",
        "source_type",
        "source_connector",
        "source_name",
        "source_provider",
        "source_format",
        "source_path",
        "source_options_json",
        "source_read_json",
        "source_request_json",
        "source_auth_json",
        "source_pagination_json",
        "source_response_json",
        "source_incremental_json",
        "source_limits_json",
        "source_capabilities_json",
        "source_metrics_json",
        "target_table",
        "mode",
        "write_engine_requested",
        "write_engine_selected",
        "write_engine_status",
        "write_engine_reason",
        "write_engine_fallback_policy",
        "status",
        "rows_read",
        "rows_written",
        "rows_inserted",
        "rows_updated",
        "rows_deleted",
        "rows_expired",
        "rows_quarantined",
        "watermark_column",
        "watermark_previous",
        "watermark_current",
        "started_at_utc",
        "finished_at_utc",
        "duration_seconds",
        "quality_status",
        "schema_policy",
        "schema_changes_json",
        "stage_durations_json",
        "contract_description",
        "contract_owner",
        "contract_domain",
        "contract_tags_json",
        "contract_sla",
        "runtime_parameters_json",
        "operation_metrics_json",
        "write_started_at_utc",
        "write_finished_at_utc",
        "table_version_before",
        "table_version_after",
        "write_committed",
        "error_message",
        "parent_run_id",
        "run_group_id",
        "master_job_id",
        "master_run_id",
        "idempotency_key",
        "idempotency_policy",
        "skip_reason",
        "skipped_by_run_id",
        "metrics_source",
        "framework_version",
        "ctrl_schema_version",
        "runtime_type",
        "engine_version",
        "python_version",
        "annotations_status",
        "annotations_result_json",
        "ownership_json",
        "operations_json",
    },
    "state": {
        "target_table",
        "watermark_column",
        "watermark_value",
        "last_success_at_utc",
        "last_run_id",
        "last_status",
        "last_rows_written",
        "last_error_message",
        "parent_run_id",
        "run_group_id",
        "master_job_id",
        "master_run_id",
        "last_table_version",
        "last_write_completed_at_utc",
        "last_watermark_candidate",
        "last_updated_at_utc",
    },
    "quality": {"run_id", "target_table", "rule_name", "status", "severity", "failed_count", "checked_at_utc", "message", "details_json"},
    "quarantine": {"run_id", "target_table", "rule_name", "error_reason", "record_payload", "quarantined_at_utc"},
    "locks": {"target_table", "run_id", "owner", "acquired_at_utc", "expires_at_utc", "ttl_minutes", "released_at_utc", "status"},
    "errors": {"run_id", "error_ts_utc", "error_date", "target_table", "source_table", "mode", "status", "error_type", "error_message", "stack_trace", "framework_version", "ctrl_schema_version", "runtime_type", "engine_version", "python_version"},
    "schema_changes": {"run_id", "change_ts_utc", "target_table", "change_type", "column_name", "source_type", "target_type", "applied", "details_json", "framework_version", "ctrl_schema_version"},
    "streams": {"stream_run_id", "idempotency_key", "idempotency_policy", "skip_reason", "skipped_by_stream_run_id", "target_table", "target_catalog", "target_layer", "runtime_entrypoint", "source_type", "source_path", "trigger", "checkpoint_location", "status", "started_at_utc", "ended_at_utc", "duration_seconds", "batches_processed", "total_rows_read", "total_rows_written", "total_rows_quarantined", "framework_version", "ctrl_schema_version", "runtime_type", "engine_version", "python_version", "error_message", "master_job_id", "master_run_id", "parent_run_id", "run_group_id"},
    "annotations": {"run_id", "target_table", "annotation_scope", "annotation_type", "column_name", "key", "previous_value", "value", "status", "error_message", "applied_sql", "annotation_ts_utc", "annotation_date", "framework_version", "ctrl_schema_version"},
    "operations": {"run_id", "target_table", "criticality", "expected_frequency", "freshness_sla_minutes", "alert_on_failure", "alert_on_quality_fail", "runbook_url", "ownership_json", "owners_json", "groups_json", "tags_json", "status", "recorded_at_utc", "framework_version", "ctrl_schema_version"},
    "access": {"access_run_id", "run_id", "target_table", "access_type", "principal", "privilege", "column_name", "function_name", "object_name", "status", "error_message", "applied_sql", "previous_value", "new_value", "mode", "drift_policy", "revoke_unmanaged", "access_ts_utc", "access_date", "framework_version", "ctrl_schema_version"},
}


def test_databricks_control_tables_preserve_contractforge_columns() -> None:
    current = {name: _column_names(columns) for name, columns in EVIDENCE_TABLE_COLUMNS.items()}
    current["state"] = _schema_names(STATE_TABLE_SCHEMAS["state"])
    current["locks"] = _schema_names(STATE_TABLE_SCHEMAS["locks"])

    missing = {
        table: sorted(columns - current.get(table, set()))
        for table, columns in CONTRACTFORGE_CONTROL_COLUMNS.items()
        if columns - current.get(table, set())
    }

    assert missing == {}


def test_databricks_diagnostics_table_preserves_explain_columns() -> None:
    sql = render_create_explain_table_sql(catalog="main", schema="ops")

    for column in ("run_id", "target_table", "source_table", "mode", "explain_format", "plan_text", "captured_at_utc"):
        assert f"{column} " in sql
        assert column in _column_names(EVIDENCE_TABLE_COLUMNS["explain"])


def test_databricks_control_tables_keep_core_observability_extensions() -> None:
    assert "source_system" in _column_names(EVIDENCE_TABLE_COLUMNS["runs"])
    assert "source_metadata_json" in _column_names(EVIDENCE_TABLE_COLUMNS["metadata"])
    assert "record_ref" in _column_names(EVIDENCE_TABLE_COLUMNS["quarantine"])
    assert "observed_value" in _column_names(EVIDENCE_TABLE_COLUMNS["quality"])


def _column_names(columns: tuple[str, ...]) -> set[str]:
    return {column.split(" ", 1)[0] for column in columns}


def _schema_names(schema: str) -> set[str]:
    return {column.strip().split(" ", 1)[0] for column in schema.split(",")}
