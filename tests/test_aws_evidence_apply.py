"""AWS in-job run-evidence write (apply) to the Iceberg control table."""

from __future__ import annotations

from contractforge_aws import render_aws_contract
from contractforge_aws.evidence.runtime import render_error_evidence_helper, render_evidence_helper
from contractforge_aws.lineage.runtime import render_lineage_helper
from contractforge_aws.evidence.metadata_runtime import render_source_metadata_helper
from contractforge_aws.schema.runtime import render_schema_change_helper
from contractforge_aws.state.runtime import render_state_helper
from contractforge_aws.evidence.stream_runtime import render_stream_batch_helper
from contractforge_aws.runtime.evidence import ensure_evidence_tables


def _job(mode: str = "scd0_append", **extra) -> str:
    c = {
        "source": {"type": "parquet", "path": "s3://landing/orders"},
        "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
        "mode": mode,
    }
    c.update(extra)
    if mode == "scd1_upsert":
        c["merge_keys"] = ["order_id"]
    job = render_aws_contract(c).artifacts["lake_bronze_orders.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    return job


def test_evidence_write_is_rendered_and_appends_run_row() -> None:
    job = _job()
    assert "def _cf_persist_run_evidence(spark, runs_table, row):" in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_runs`" in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_errors`" in job
    assert ".snapshots ORDER BY committed_at DESC LIMIT 1" in job
    assert "_cf_persist_run_evidence(" in job
    assert "INSERT INTO" in job
    assert job.index("job.commit()") < job.index("_cf_persist_run_evidence(\n")


def test_error_evidence_is_rendered_and_reraises_failures() -> None:
    job = _job()

    assert "def _cf_persist_error_evidence(spark, errors_table, row):" in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_errors`" in job
    assert "try:" in job
    assert "except Exception as _cf_exc:" in job
    assert "    try:\n        # Persist failure evidence to the Iceberg error control table, then re-raise." in job
    assert "except Exception as _cf_evidence_exc:" in job
    assert "ContractForge AWS error evidence write failed: " in job
    assert "'status': 'FAILED'," in job
    assert "# Persist failed run evidence after error evidence is recorded." in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_runs`" in job
    assert "'write_engine_status': 'FAILED'," in job
    assert "'metrics_source': 'glue_exception'," in job
    assert "'write_committed': False," in job
    assert "_cf_failure_write_started_at = globals().get('_cf_write_started_at')" in job
    assert "_cf_failure_write_finished_at = globals().get('_cf_write_finished_at') or (_cf_failure_finished_at if _cf_failure_write_started_at else None)" in job
    assert "'write_started_at_utc': _cf_failure_write_started_at.strftime('%Y-%m-%d %H:%M:%S') if _cf_failure_write_started_at else None," in job
    assert "'write_finished_at_utc': _cf_failure_write_finished_at.strftime('%Y-%m-%d %H:%M:%S') if _cf_failure_write_finished_at else None," in job
    assert "_cf_error_message = _cf_redact_error_text(str(_cf_exc))" in job
    assert "_cf_stack_trace = _cf_redact_error_text(traceback.format_exc())" in job
    assert "'error_message': _cf_error_message," in job
    assert "'stack_trace': _cf_stack_trace," in job
    assert "from contractforge_core.security import redact_text as _redact_text" in job
    assert "import re as _cf_re" in job
    assert "Bearer|Basic" in job
    assert "REDACTED" in job
    assert "'error_message': str(_cf_exc)," not in job
    assert "traceback.format_exc()" in job
    assert "    raise" in job
    assert job.index("def _cf_persist_run_evidence") < job.index("\ntry:\n    # Ensure target namespace")
    assert job.index("# Persist failure evidence to the Iceberg error control table") < job.index("# Persist failed run evidence")


def test_evidence_write_fills_neutral_columns() -> None:
    job = _job()
    assert "'table_version_after': (str(_cf_snapshots[0]['snapshot_id']) if _cf_snapshots else None)," in job
    assert "'rows_read': _cf_rows_read," in job
    assert "_cf_rows_read = int(df.count())" in job
    assert "_cf_rows_read = _cf_rows_read" in job
    assert (
        "'rows_written': int(_cf_summary.get('contractforge_rows_written') "
        "if _cf_summary.get('contractforge_rows_written') is not None else "
        "(_cf_summary.get('added-records') or 0)),"
    ) in job
    assert "'rows_inserted': int(_cf_summary.get('added-records') or 0)," in job
    assert "'write_engine_selected': 'aws_glue_iceberg'," in job
    assert "'status': globals().get('_cf_run_status', 'SUCCESS')," in job
    assert "'write_engine_status': globals().get('_cf_write_engine_status', 'SUPPORTED')," in job
    assert "'skip_reason': globals().get('_cf_skip_reason')," in job
    assert (
        "'write_committed': not bool(globals().get('_cf_no_input_skip', False) "
        "or globals().get('_cf_skip_reason') == 'no_hash_changes'),"
    ) in job
    assert "'runtime_type': 'aws_glue'," in job
    assert "'runtime_entrypoint': args['JOB_NAME']," in job
    assert "_cf_master_job_id = _cf_runtime_arg('CONTRACTFORGE_MASTER_JOB_ID') or args['JOB_NAME']" in job
    assert "_cf_master_run_id = _cf_runtime_arg('CONTRACTFORGE_MASTER_RUN_ID') or _cf_job_run_id" in job
    assert "'master_job_id': None or _cf_master_job_id," in job
    assert "'master_run_id': None or _cf_master_run_id," in job
    assert "_cf_write_started_at = datetime.now(timezone.utc)" in job
    assert "_cf_write_finished_at = datetime.now(timezone.utc)" in job
    assert "_cf_success_write_started_at = globals().get('_cf_write_started_at') or _cf_run_now" in job
    assert "_cf_success_write_finished_at = globals().get('_cf_write_finished_at') or _cf_finished_at" in job
    assert "'write_started_at_utc': _cf_success_write_started_at.strftime('%Y-%m-%d %H:%M:%S')," in job
    assert "'write_finished_at_utc': _cf_success_write_finished_at.strftime('%Y-%m-%d %H:%M:%S')," in job
    assert "'source_type': 'parquet'," in job
    assert "'source_format': 'parquet'," in job
    assert "'source_path': 's3://landing/orders'," in job
    assert "'source_capabilities_json': {'adapter': 'aws', 'source_type': 'parquet', 'status': 'SUPPORTED'" in job
    assert "'source_metrics_json': {'rows_read': _cf_rows_read}," in job
    assert "'engine_version': _cf_spark_version," in job
    assert "'python_version': _cf_python_version," in job
    assert "'ctrl_schema_version': 1," in job
    assert "'operation_metrics_json': _cf_summary," in job
    assert "'hash_diff_candidate_rows': globals().get('_cf_hash_diff_candidate_rows')," in job
    assert "'hash_input_columns': globals().get('_cf_hash_input_columns')," in job
    assert "'schema_changes_json': globals().get('_cf_schema_changes')," in job
    # the runs DDL uses the neutral, portabilized schema
    assert "`table_version_after` STRING" in job
    assert "`runtime_entrypoint` STRING" in job
    assert "`engine_version` STRING" in job


def test_batch_rows_read_is_captured_before_quality_can_filter_rows() -> None:
    job = _job(quality_rules={"not_null": ["order_id"]})

    assert job.index("_cf_rows_read = int(df.count())") < job.index("# Native Glue Data Quality evaluation")
    assert job.index("_cf_rows_read = _cf_rows_read") > job.index("job.commit()")
    assert job.index("_cf_rows_read = _cf_rows_read") < job.index("_cf_persist_run_evidence(\n")


def test_evidence_write_fills_source_detail_json_columns() -> None:
    job = _job(
        source={
            "type": "rest_api",
            "request": {"url": "https://api.example.com/orders", "headers": {"X-Trace": "orders"}},
            "auth": {"type": "bearer_token", "token": "{{ secret:api/token }}"},
            "pagination": {"type": "offset", "limit_param": "limit"},
            "response": {"records_path": "$.items"},
            "limits": {"max_records": 10},
        }
    )

    assert "'source_request_json': {'url': 'https://api.example.com/orders', 'headers': {'X-Trace': 'orders'}}" in job
    assert "'source_auth_json': {'type': 'bearer_token', 'token': '***REDACTED***'}" in job
    assert "'source_pagination_json': {'type': 'offset', 'limit_param': 'limit'}" in job
    assert "'source_response_json': {'records_path': '$.items'}" in job
    assert "'source_limits_json': {'max_records': 10}" in job


def test_evidence_write_fills_operations_and_ownership_columns() -> None:
    job = _job(
        operations={
            "criticality": "high",
            "freshness_sla_minutes": 30,
            "ownership": {"technical_owner": "data-eng"},
            "tags": {"tier": "gold"},
        },
        annotations={"table": {"description": "Orders table"}},
        domain="commerce",
        runtime_parameters={"worker_type": "G.1X"},
        idempotency_key="orders-2026-01-01",
        run_group_id="group-1",
    )

    assert "'contract_description': 'Orders table'," in job
    assert "'contract_owner': 'data-eng'," in job
    assert "'contract_domain': 'commerce'," in job
    assert "'contract_tags_json': {'tier': 'gold'}," in job
    assert "'contract_sla': '30'," in job
    assert "'runtime_parameters_json': {'worker_type': 'G.1X'}," in job
    assert "'ownership_json': {'technical_owner': 'data-eng'}," in job
    assert "'operations_json': {'metadata':" in job
    assert "'idempotency_key': 'orders-2026-01-01'," in job
    assert "'run_group_id': 'group-1' or _cf_run_group_id," in job


def test_contract_master_ids_override_glue_runtime_defaults() -> None:
    job = _job(
        master_job_id="external-master-job",
        master_run_id="external-master-run",
    )

    assert "'master_job_id': 'external-master-job' or _cf_master_job_id," in job
    assert "'master_run_id': 'external-master-run' or _cf_master_run_id," in job


def test_lineage_evidence_is_rendered_before_final_run_evidence() -> None:
    job = _job()
    assert "def _cf_persist_lineage_evidence(spark, lineage_table, row):" in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_lineage`" in job
    assert "'schemaURL': 'https://openlineage.io/spec/1-0-5/OpenLineage.json'," in job
    assert "'icebergSnapshotAfter': _cf_lineage_snapshot_after," in job
    assert "_cf_persist_lineage_evidence(" in job
    assert job.index("job.commit()") < job.index("_cf_persist_lineage_evidence(\n")
    assert job.index("_cf_persist_lineage_evidence(\n") < job.index("_cf_persist_run_evidence(\n")


def test_source_metadata_evidence_is_rendered_before_final_run_evidence() -> None:
    job = _job()
    assert "def _cf_persist_source_metadata_evidence(spark, metadata_table, row):" in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_metadata`" in job
    assert "'component': 'source'," in job
    assert "'framework_version': 'contractforge-aws'," in job
    assert "'source_metadata_json': _cf_source_metadata," in job
    assert "_cf_source_metadata.setdefault('source_metrics', {})['rows_read'] = _cf_rows_read" in job
    assert "_cf_source_metadata.setdefault('source_metrics', {})['columns_read'] = len(df.columns)" in job
    assert "'source_schema'] = {" in job
    assert "'type': field.dataType.simpleString()," in job
    assert job.index("job.commit()") < job.index("_cf_persist_source_metadata_evidence(\n")
    assert job.index("_cf_persist_source_metadata_evidence(\n") < job.index("_cf_persist_run_evidence(\n")


def test_state_update_is_rendered_before_final_run_evidence() -> None:
    job = _job()
    assert "def _cf_record_state(spark, state_table, row):" in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_state`" in job
    assert "'last_run_id': _cf_run_id," in job
    assert "_cf_state_status = globals().get('_cf_run_status', 'SUCCESS')" in job
    assert "_cf_state_success_ts = _cf_finished_at.strftime('%Y-%m-%d %H:%M:%S') if _cf_state_status == 'SUCCESS' else None" in job
    assert "'last_status': _cf_state_status," in job
    assert "'last_success_at_utc': _cf_state_success_ts," in job
    assert "'last_write_completed_at_utc': _cf_state_write_completed_ts," in job
    assert "'last_table_version': _cf_state_last_table_version," in job
    assert "spark.sql('INSERT INTO ' + state_table + ' SELECT ' + select_sql)" in job
    assert "MERGE INTO ' + state_table" not in job
    assert job.index("job.commit()") < job.index("_cf_record_state(\n")
    assert job.index("_cf_record_state(\n") < job.index("_cf_persist_run_evidence(\n")


def test_state_update_records_batch_watermark_candidate() -> None:
    job = _job(source={"type": "parquet", "path": "s3://landing/orders", "incremental": {"watermark_column": "updated_at"}})
    assert "_cf_state_watermark_column = 'updated_at'" in job
    assert "if _cf_state_watermark_column and _cf_state_watermark_column in df.columns:" in job
    assert "df.selectExpr(_cf_state_watermark_expr).collect()" in job
    assert "'watermark_value': _cf_state_watermark_value," in job
    assert "'last_watermark_candidate': _cf_state_watermark_value," in job


def test_schema_change_evidence_is_rendered_before_run_evidence() -> None:
    job = _job()
    assert "def _cf_persist_schema_change_evidence(spark, table, run_id, target_table, schema_after, changes):" in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_schema_changes`" in job
    assert "_cf_schema_before = _cf_describe_table_schema(spark, _cf_target_table)" in job
    assert "_cf_schema_changes = {'added_columns': _cf_schema_added, 'type_changes': _cf_schema_type_changes}" in job
    assert "_cf_persist_schema_change_evidence(" in job
    assert job.index("_cf_schema_before = _cf_describe_table_schema") < job.index("# Write target intent.")
    schema_change_call = job.rindex("_cf_persist_schema_change_evidence(")
    assert job.index("job.commit()") < schema_change_call
    assert schema_change_call < job.index("_cf_persist_run_evidence(\n")


def test_evidence_write_for_upsert_mode() -> None:
    job = _job(mode="scd1_upsert")
    assert "'mode': 'scd1_upsert'," in job
    assert "_cf_persist_run_evidence(" in job


def test_evidence_helper_is_valid_python() -> None:
    compile(render_evidence_helper(), "helper.py", "exec")
    compile(render_error_evidence_helper(), "error_helper.py", "exec")
    compile(render_lineage_helper(), "lineage_helper.py", "exec")
    compile(render_source_metadata_helper(), "metadata_helper.py", "exec")
    compile(render_state_helper(), "state_helper.py", "exec")
    compile(render_stream_batch_helper(), "stream_helper.py", "exec")
    compile(render_schema_change_helper(), "schema_helper.py", "exec")


def test_error_evidence_helper_fallback_redacts_without_core_dependency() -> None:
    namespace: dict[str, object] = {}
    exec(render_error_evidence_helper(), namespace)
    redact = namespace["_cf_redact_error_text"]

    message = redact("jdbc:postgresql://user:pass@host/db password=raw Bearer abc123")

    assert "pass@host" not in message
    assert "password=raw" not in message
    assert "Bearer abc123" not in message
    assert "***REDACTED***" in message


def test_evidence_helper_writes_full_runs_schema_with_null_defaults() -> None:
    helper = render_evidence_helper()

    assert "_CF_RUN_COLUMNS" in helper
    assert "'source_system'" in helper
    assert "'metrics_json'" in helper
    assert "normalized = {column: row.get(column) for column in _CF_RUN_COLUMNS}" in helper


def test_evidence_setup_reports_partial_progress_on_failure() -> None:
    class FailingRunner:
        def __init__(self) -> None:
            self.statements: list[str] = []

        def sql(self, statement: str) -> None:
            self.statements.append(statement)
            if len(self.statements) == 3:
                raise RuntimeError("athena failed password=raw-secret token=raw-token")

    runner = FailingRunner()
    result = ensure_evidence_tables(runner=runner, database="ops")

    assert result.status == "FAILED"
    assert result.statements_executed == 2
    assert result.error is not None
    assert result.error.startswith("athena failed")
    assert "raw-secret" not in result.error
    assert "raw-token" not in result.error
    assert "***REDACTED***" in result.error


def test_error_evidence_helper_writes_full_errors_schema_with_null_defaults() -> None:
    helper = render_error_evidence_helper()

    assert "_CF_ERROR_COLUMNS" in helper
    assert "'error_class'" in helper
    assert "'python_version'" in helper
    assert "normalized = {column: row.get(column) for column in _CF_ERROR_COLUMNS}" in helper


def test_streaming_job_also_writes_run_evidence_after_termination() -> None:
    artifacts = render_aws_contract(
        {
            "source": {
                "type": "kafka_available_now",
                "bootstrap_servers": "b:9092",
                "topic": "events",
                "checkpoint_location": "s3://c/p",
            },
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
        }
    )
    job = artifacts.artifacts["lake_bronze_events.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    assert "def _cf_persist_error_evidence(spark, errors_table, row):" in job
    assert "except Exception as _cf_exc:" in job
    assert "except Exception as _cf_evidence_exc:" in job
    assert "# Persist failed run evidence after error evidence is recorded." in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_errors`" in job
    assert "_cf_persist_run_evidence(" in job
    assert "_cf_persist_source_metadata_evidence(" in job
    assert "_cf_source_metadata.setdefault('source_metrics', {})['columns_read'] = len(source_stream.columns)" in job
    assert "for field in source_stream.schema.fields" in job
    assert "_cf_persist_lineage_evidence(" in job
    assert "_cf_persist_schema_change_evidence(" in job
    assert "_cf_persist_stream_batch_evidence(" in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_streams`" in job
    assert "_cf_rows_read = int(_cf_stream_totals.get('rows_read', 0))" in job
    assert "'stream_batches': int(_cf_stream_totals.get('batches', 0))" in job
    assert "'stream_rows_written': int(_cf_stream_totals.get('rows_written', 0))" in job
    assert "'contractforge_rows_written': int(_cf_stream_totals.get('rows_written', 0))" in job
    assert "_cf_lineage_rows_written = int(" in job
    assert "_cf_state_rows_written = int(" in job
    assert "'master_job_id': None or _cf_master_job_id," in job
    assert "'master_run_id': None or _cf_master_run_id," in job
    assert "df.selectExpr(_cf_state_watermark_expr)" not in job
    assert job.index("query.awaitTermination()") < job.index("job.commit()")
    assert job.index("job.commit()") < job.index("_cf_persist_run_evidence(\n")


def test_streaming_batch_evidence_records_contract_run_group_metadata() -> None:
    artifacts = render_aws_contract(
        {
            "source": {
                "type": "kafka_available_now",
                "bootstrap_servers": "b:9092",
                "topic": "events",
                "checkpoint_location": "s3://c/p",
            },
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
            "parent_run_id": "parent-1",
            "run_group_id": "group-1",
            "master_job_id": "master-job",
            "master_run_id": "master-run",
        }
    )
    job = artifacts.artifacts["lake_bronze_events.glue_job.py"]
    compile(job, "glue_job.py", "exec")

    assert "'master_job_id': 'master-job' or _cf_master_job_id," in job
    assert "'master_run_id': 'master-run' or _cf_master_run_id," in job
    assert "'parent_run_id': 'parent-1' or _cf_parent_run_id," in job
    assert "'run_group_id': 'group-1' or _cf_run_group_id," in job
