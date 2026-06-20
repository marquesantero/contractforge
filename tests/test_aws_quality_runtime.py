"""Native Glue Data Quality evaluation + per-rule quality evidence (AWS)."""

from __future__ import annotations

from contractforge_aws import render_aws_contract
from contractforge_aws.quality.runtime import render_quality_evidence_helper


def _job(quality_rules: dict, mode: str = "scd0_append") -> str:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": mode,
            "quality_rules": quality_rules,
        }
    ).artifacts
    return artifacts["lake_bronze_orders.glue_job.py"]


def test_abort_rules_evaluate_and_raise() -> None:
    job = _job({"required_columns": ["order_id"], "unique_key": ["order_id"], "min_rows": 1})
    compile(job, "j", "exec")
    assert "from awsgluedq.transforms import EvaluateDataQuality" in job
    assert "# Quality rules with 'abort' enforcement." in job
    assert "ColumnExists" in job and "IsUnique" in job and "RowCount >= 1" in job
    assert "_cf_dq_abort_outcomes = _cf_dq_abort_results.toDF().collect()" in job
    assert "SelectFromCollection.apply(dfc=_cf_dq_abort_results" not in job
    assert "raise ValueError('Data quality (abort) failed: '" in job
    assert "# Quality rules with 'warn' enforcement." not in job


def test_row_level_quarantine_rules_filter_and_record_quarantine() -> None:
    job = _job({"not_null": ["order_id"], "accepted_values": {"status": ["A", "B"]}})
    compile(job, "j", "exec")
    assert "# Quality rules with 'quarantine' enforcement (row-level)" in job
    assert "ctrl_ingestion_quarantine" in job
    assert "EvaluateDataQuality().process_rows(" in job
    assert "key='rowLevelOutcomes'" in job
    assert "DataQualityEvaluationResult = 'Failed'" in job
    assert "DataQualityEvaluationResult = 'Passed'" in job
    assert "globals()['_cf_rows_quarantined'] = _cf_rows_quarantined" in job
    assert "_cf_update_quality_status('QUARANTINED')" in job
    assert "Data quality (abort) failed" not in job


def test_warn_rules_record_without_filtering() -> None:
    job = _job({"max_null_ratio": {"email": 0.05}})
    compile(job, "j", "exec")
    assert "# Quality rules with 'warn' enforcement." in job
    assert "print('Data quality (warn) failures recorded: '" in job
    assert "_cf_update_quality_status('WARNED')" in job
    assert "key='rowLevelOutcomes'" not in job


def test_quality_evidence_is_persisted_to_control_table() -> None:
    job = _job({"required_columns": ["order_id"]})
    assert "ctrl_ingestion_quality" in job
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_quality`" in job
    assert "_cf_persist_quality_evidence(spark, 'glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_quality`', _cf_run_id," in job


def test_run_evidence_records_quarantined_row_count() -> None:
    job = _job({"not_null": ["order_id"]})
    assert "'rows_quarantined': int(globals().get('_cf_rows_quarantined', 0))" in job
    assert "'quality_status': globals().get('_cf_quality_status', 'PASSED')" in job


def test_run_evidence_marks_quality_not_configured_without_rules() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    ).artifacts
    job = artifacts["lake_bronze_orders.glue_job.py"]
    assert "'quality_status': globals().get('_cf_quality_status', 'NOT_CONFIGURED')" in job


def test_run_and_quality_evidence_share_run_id() -> None:
    job = _job({"required_columns": ["order_id"]})
    # the shared run identity is defined once in the preamble
    assert "_cf_job_run_id = _cf_runtime_arg('JOB_RUN_ID')" in job
    assert "_cf_run_id_suffix = _cf_job_run_id or" in job
    assert "_cf_run_id = args['JOB_NAME'] + ':' + _cf_run_id_suffix" in job
    # both the run evidence and the quality evidence reference it
    assert "'run_id': _cf_run_id," in job
    assert "_cf_run_id, 'glue_catalog.lake_bronze.orders'" in job


def test_quality_helper_is_valid_python() -> None:
    compile(render_quality_evidence_helper(), "helper.py", "exec")


def test_expression_quality_renders_as_spark_sql_runtime_check() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "quality_rules": {"expressions": [{"name": "amount_positive", "expression": "amount > 0"}]},
        }
    ).artifacts
    job = artifacts["lake_bronze_orders.glue_job.py"]
    compile(job, "j", "exec")
    assert "# Spark SQL quality expression: amount_positive" in job
    assert "_cf_expr_amount_positive_failed = df.filter('NOT (amount > 0) OR (amount > 0) IS NULL')" in job
    assert "_cf_persist_quality_evidence(" in job
    assert "_cf_update_quality_status('QUARANTINED')" in job
    assert "df = df.filter('(amount > 0)')" in job
    assert "ctrl_ingestion_quarantine" in job


def test_expression_quality_abort_raises() -> None:
    job = _job({"expressions": [{"name": "amount_positive", "expression": "amount > 0", "severity": "abort"}]})
    compile(job, "j", "exec")
    assert "raise ValueError('Data quality expression failed: amount_positive')" in job
    assert "_cf_update_quality_status('FAILED')" in job


def test_streaming_job_evaluates_quality_inside_foreachbatch() -> None:
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
            "quality_rules": {"required_columns": ["id"]},
        }
    ).artifacts
    job = artifacts["lake_bronze_events.glue_job.py"]
    compile(job, "j", "exec")
    assert "EvaluateDataQuality.apply(" in job
    assert "globals()['_cf_rows_quarantined'] = 0" in job
    # the quality-evidence helper is defined before the streaming query consumes it
    assert job.index("def _cf_persist_quality_evidence") < job.index("def _process_batch")
