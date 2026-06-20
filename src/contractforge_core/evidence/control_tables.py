"""Platform-neutral ContractForge control table schemas."""

from __future__ import annotations

EVIDENCE_TABLES = {
    "runs": "ctrl_ingestion_runs",
    "errors": "ctrl_ingestion_errors",
    "quality": "ctrl_ingestion_quality",
    "quarantine": "ctrl_ingestion_quarantine",
    "schema_changes": "ctrl_ingestion_schema_changes",
    "lineage": "ctrl_ingestion_lineage",
    "explain": "ctrl_ingestion_explain",
    "metadata": "ctrl_ingestion_metadata",
    "streams": "ctrl_ingestion_streams",
    "annotations": "ctrl_ingestion_annotations",
    "access": "ctrl_ingestion_access",
    "operations": "ctrl_ingestion_operations",
    "cost": "ctrl_ingestion_cost",
    "deployments": "ctrl_deployment_versions",
}

STATE_TABLES = {
    "state": "ctrl_ingestion_state",
    "locks": "ctrl_ingestion_locks",
}

_EVIDENCE_SCHEMA_TEXT = {
    "runs": """
        run_id STRING, run_ts_utc TIMESTAMP, run_date DATE, runtime_entrypoint STRING, layer STRING,
        source_table STRING, source_type STRING, source_connector STRING, source_name STRING,
        source_system STRING,
        source_provider STRING, source_format STRING, source_path STRING, source_options_json STRING,
        source_read_json STRING, source_request_json STRING, source_auth_json STRING,
        source_pagination_json STRING, source_response_json STRING, source_incremental_json STRING,
        source_limits_json STRING, source_capabilities_json STRING, source_metrics_json STRING,
        target_table STRING, mode STRING, write_engine_requested STRING, write_engine_selected STRING,
        write_engine_status STRING, write_engine_reason STRING, write_engine_fallback_policy STRING,
        status STRING, rows_read BIGINT, rows_written BIGINT, rows_inserted BIGINT,
        rows_updated BIGINT, rows_deleted BIGINT, rows_expired BIGINT, rows_quarantined BIGINT,
        watermark_column STRING, watermark_previous STRING, watermark_current STRING,
        started_at_utc TIMESTAMP, finished_at_utc TIMESTAMP, duration_seconds DOUBLE,
        quality_status STRING, schema_policy STRING, schema_changes_json STRING,
        stage_durations_json STRING, contract_description STRING, contract_owner STRING,
        contract_domain STRING, contract_tags_json STRING, contract_sla STRING,
        runtime_parameters_json STRING, operation_metrics_json STRING, write_started_at_utc TIMESTAMP,
        write_finished_at_utc TIMESTAMP, table_version_before STRING, table_version_after STRING,
        write_committed BOOLEAN, error_message STRING, parent_run_id STRING, run_group_id STRING,
        master_job_id STRING, master_run_id STRING, idempotency_key STRING, idempotency_policy STRING,
        skip_reason STRING, skipped_by_run_id STRING, metrics_source STRING, framework_version STRING,
        ctrl_schema_version BIGINT, runtime_type STRING, engine_version STRING, python_version STRING,
        annotations_status STRING, annotations_result_json STRING, ownership_json STRING,
        operations_json STRING, metrics_json STRING
    """,
    "errors": """
        run_id STRING, error_ts_utc TIMESTAMP, error_date DATE, target_table STRING,
        source_table STRING, mode STRING, status STRING, error_type STRING, error_class STRING,
        error_message STRING, stack_trace STRING, occurred_at_utc TIMESTAMP, framework_version STRING,
        ctrl_schema_version BIGINT, runtime_type STRING, engine_version STRING, python_version STRING
    """,
    "quality": """
        run_id STRING, target_table STRING, rule_name STRING, status STRING, severity STRING,
        failed_count BIGINT, observed_value STRING, checked_at_utc TIMESTAMP, message STRING,
        details_json STRING
    """,
    "quarantine": """
        run_id STRING, target_table STRING, rule_name STRING, error_reason STRING,
        record_payload STRING, record_ref STRING, reason STRING, quarantined_at_utc TIMESTAMP
    """,
    "schema_changes": """
        run_id STRING, change_ts_utc TIMESTAMP, target_table STRING, change_type STRING,
        column_name STRING, source_type STRING, target_type STRING, applied BOOLEAN,
        details_json STRING, payload_json STRING, changed_at_utc TIMESTAMP, framework_version STRING,
        ctrl_schema_version BIGINT
    """,
    "lineage": """
        run_id STRING, event_time_utc TIMESTAMP, event_type STRING, target_table STRING,
        source_table STRING, source_name STRING, namespace STRING, producer STRING, event_json STRING
    """,
    "explain": """
        run_id STRING, target_table STRING, source_table STRING, mode STRING,
        explain_format STRING, plan_text STRING, captured_at_utc TIMESTAMP
    """,
    "metadata": """
        component STRING, framework_version STRING, ctrl_schema_version BIGINT, updated_at_utc TIMESTAMP,
        run_id STRING, target_table STRING, source_metadata_json STRING, captured_at_utc TIMESTAMP
    """,
    "streams": """
        stream_run_id STRING, run_id STRING, idempotency_key STRING, idempotency_policy STRING,
        skip_reason STRING, skipped_by_stream_run_id STRING, target_table STRING, target_catalog STRING,
        target_layer STRING, runtime_entrypoint STRING, source_type STRING, source_path STRING,
        trigger STRING, checkpoint_location STRING, status STRING, started_at_utc TIMESTAMP,
        ended_at_utc TIMESTAMP, duration_seconds DOUBLE, batches_processed BIGINT,
        total_rows_read BIGINT, total_rows_written BIGINT, total_rows_quarantined BIGINT,
        batch_id STRING, batch_metrics_json STRING, captured_at_utc TIMESTAMP, framework_version STRING,
        ctrl_schema_version BIGINT, runtime_type STRING, engine_version STRING, python_version STRING,
        error_message STRING, master_job_id STRING, master_run_id STRING, parent_run_id STRING,
        run_group_id STRING
    """,
    "annotations": """
        run_id STRING, target_table STRING, annotation_scope STRING, annotation_type STRING,
        column_name STRING, key STRING, previous_value STRING, value STRING, status STRING,
        error_message STRING, applied_sql STRING, annotation_ts_utc TIMESTAMP, annotation_date DATE,
        framework_version STRING, ctrl_schema_version BIGINT
    """,
    "access": """
        access_run_id STRING, run_id STRING, target_table STRING, action STRING, access_type STRING,
        principal STRING, privilege STRING, column_name STRING, function_name STRING, object_name STRING,
        status STRING, error_message STRING, applied_sql STRING, previous_value STRING, new_value STRING,
        mode STRING, drift_policy STRING, revoke_unmanaged BOOLEAN, access_ts_utc TIMESTAMP,
        access_date DATE, payload_json STRING, applied_at_utc TIMESTAMP, framework_version STRING,
        ctrl_schema_version BIGINT
    """,
    "operations": """
        run_id STRING, target_table STRING, criticality STRING, expected_frequency STRING,
        freshness_sla_minutes BIGINT, alert_on_failure BOOLEAN, alert_on_quality_fail BOOLEAN,
        runbook_url STRING, ownership_json STRING, owners_json STRING, groups_json STRING,
        tags_json STRING, status STRING, recorded_at_utc TIMESTAMP, framework_version STRING,
        ctrl_schema_version BIGINT
    """,
    "cost": """
        run_id STRING, target_table STRING, signal_name STRING, signal_value DOUBLE,
        payload_json STRING, captured_at_utc TIMESTAMP
    """,
    "deployments": """
        deployment_id STRING NOT NULL, deployment_step_id STRING NOT NULL,
        deployment_hash STRING NOT NULL, deployment_ts_utc TIMESTAMP, deployment_date DATE,
        deployment_status STRING, adapter STRING, platform STRING, subtarget STRING,
        project_name STRING, project_path STRING, environment_key STRING, environment_path STRING,
        contract_name STRING, contract_path STRING, contract_layer STRING, target_table STRING,
        mode STRING, action STRING, artifact_kind STRING, artifact_name STRING, artifact_id STRING,
        artifact_uri STRING, definition_hash STRING, previous_definition_hash STRING,
        contract_hash STRING, environment_hash STRING, manifest_hash STRING,
        package_versions_json STRING, git_commit STRING, deployed_by STRING,
        deployment_config_json STRING, deployment_result_json STRING, created_at_utc TIMESTAMP,
        framework_version STRING, ctrl_schema_version BIGINT
    """,
}

_STATE_SCHEMA_TEXT = {
    "state": """
        target_table STRING NOT NULL, watermark_column STRING, watermark_value STRING,
        last_success_at_utc TIMESTAMP, last_run_id STRING, last_status STRING,
        last_rows_written BIGINT, last_error_message STRING, parent_run_id STRING,
        run_group_id STRING, master_job_id STRING, master_run_id STRING, last_table_version STRING,
        last_write_completed_at_utc TIMESTAMP, last_watermark_candidate STRING, last_updated_at_utc TIMESTAMP
    """,
    "locks": """
        target_table STRING NOT NULL, run_id STRING, owner STRING, acquired_at_utc TIMESTAMP,
        expires_at_utc TIMESTAMP, ttl_minutes BIGINT, released_at_utc TIMESTAMP, status STRING
    """,
}


def _columns(schema: str) -> tuple[str, ...]:
    return tuple(column.strip() for column in " ".join(schema.split()).split(",") if column.strip())


EVIDENCE_TABLE_COLUMNS = {table: _columns(schema) for table, schema in _EVIDENCE_SCHEMA_TEXT.items()}
EVIDENCE_TABLE_SCHEMAS = {table: ", ".join(columns) for table, columns in EVIDENCE_TABLE_COLUMNS.items()}
STATE_TABLE_COLUMNS = {table: _columns(schema) for table, schema in _STATE_SCHEMA_TEXT.items()}
STATE_TABLE_SCHEMAS = {table: ", ".join(columns) for table, columns in STATE_TABLE_COLUMNS.items()}
