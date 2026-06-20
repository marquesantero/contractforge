from datetime import datetime

from contractforge_databricks.evidence import (
    AccessEvidenceRecord,
    CostEvidenceRecord,
    EvidenceWriter,
    LineageEvidenceRecord,
    QualityEvidenceRecord,
    QuarantineEvidenceRecord,
    RunEvidenceRecord,
    SchemaChangeEvidenceRecord,
    SourceMetadataEvidenceRecord,
    StreamBatchEvidenceRecord,
    render_access_insert_sql,
    render_cost_insert_sql,
    render_lineage_insert_sql,
    render_run_insert_sql,
    render_run_log_insert_sql,
    render_quality_insert_sql,
    render_quarantine_insert_sql,
    render_schema_change_insert_sql,
    render_source_metadata_insert_sql,
    render_stream_batch_insert_sql,
)


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def test_render_run_insert_sql() -> None:
    record = RunEvidenceRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        mode="scd1_upsert",
        status="SUCCESS",
        started_at_utc=datetime(2026, 1, 1, 12, 0, 0),
        finished_at_utc=datetime(2026, 1, 1, 12, 1, 0),
        metrics={"rows": 10},
    )

    sql = render_run_insert_sql(record)

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_runs`" in sql
    assert "'scd1_upsert'" in sql
    assert '\'{"rows":10}\'' in sql


def test_render_run_log_insert_sql_with_full_control_payload() -> None:
    sql = render_run_log_insert_sql(
        {
            "run_id": "run-1",
            "run_ts_utc": datetime(2026, 1, 1, 12, 0, 0),
            "run_date": "2026-01-01",
            "target": {"table": "main.silver.orders"},
            "mode": "scd2_historical",
            "status": "SUCCESS",
            "source_type": "jdbc",
            "source_connector": "postgres",
            "source_system": "crm",
            "source_auth_json": {"password": "raw-secret"},
            "write_engine_selected": "delta_merge",
            "write_engine_status": "contractforge_algorithm",
            "rows_read": "10",
            "rows_written": 8,
            "rows_expired": 2,
            "table_version_before": "41",
            "table_version_after": "42",
            "write_committed": True,
            "idempotency_key": "orders:2026-01-01",
            "operation_metrics_json": {"numTargetRowsInserted": "8"},
            "error_message": "password=raw-secret",
        }
    )

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_runs`" in sql
    assert "source_capabilities_json" in sql
    assert "source_system" in sql
    assert "'crm'" in sql
    assert "'scd2_historical'" in sql
    assert "table_version_after" in sql
    assert "42" in sql
    assert "true" in sql
    assert "raw-secret" not in sql
    assert "***REDACTED***" in sql


def test_render_lineage_insert_sql() -> None:
    record = LineageEvidenceRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        source_name="postgres.public.orders",
        event={"source": "postgres"},
        event_time_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    sql = render_lineage_insert_sql(record)

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_lineage`" in sql
    assert "'postgres.public.orders'" in sql


def test_evidence_writer_uses_runner() -> None:
    runner = FakeRunner()
    writer = EvidenceWriter(runner)
    record = RunEvidenceRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        mode="scd0_append",
        status="SUCCESS",
        started_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    writer.write_run(record)

    assert len(runner.statements) == 1
    assert "ctrl_ingestion_runs" in runner.statements[0]


def test_evidence_writer_can_write_full_run_log() -> None:
    runner = FakeRunner()
    writer = EvidenceWriter(runner)

    writer.write_run_log({"run_id": "run-1", "target_table": "main.silver.orders", "rows_read": 1})

    assert len(runner.statements) == 1
    assert "rows_read" in runner.statements[0]


def test_render_quality_insert_sql() -> None:
    record = QualityEvidenceRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        rule_name="order_id_not_null",
        status="PASSED",
        observed_value="0",
        checked_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    sql = render_quality_insert_sql(record)

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_quality`" in sql
    assert "'order_id_not_null'" in sql


def test_render_quality_results_insert_sql_uses_full_control_payload() -> None:
    from contractforge_databricks.quality import render_quality_results_insert_sql
    from contractforge_core.quality import QualityRuleResult

    sql = render_quality_results_insert_sql(
        run_id="run-1",
        target_table="main.silver.orders",
        results=(
            QualityRuleResult(
                "not_null_order_id",
                "FAILED",
                failed_count=2,
                severity="abort",
                message="missing order_id",
                details={"column": "order_id"},
            ),
        ),
        checked_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert "ctrl_ingestion_quality" in sql
    assert "severity, failed_count, observed_value" in sql
    assert "'abort'" in sql
    assert "2" in sql
    assert "missing order_id" in sql
    assert '"column":"order_id"' in sql


def test_render_schema_change_insert_sql() -> None:
    record = SchemaChangeEvidenceRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        change_type="additive_columns",
        payload={"columns": ["ingested_at"]},
        changed_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    sql = render_schema_change_insert_sql(record)

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_schema_changes`" in sql
    assert "'additive_columns'" in sql
    assert '\'{"columns":["ingested_at"]}\'' in sql


def test_render_cost_insert_sql() -> None:
    record = CostEvidenceRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        signal_name="dbus_estimated",
        signal_value=1.25,
        payload={"cluster_id": "abc"},
        captured_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    sql = render_cost_insert_sql(record)

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_cost`" in sql
    assert "'dbus_estimated'" in sql
    assert "1.25" in sql


def test_render_remaining_evidence_insert_sql() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0)

    quarantine = render_quarantine_insert_sql(
        QuarantineEvidenceRecord("run-1", "main.silver.orders", "dbfs:/q/1.json", "not_null", now)
    )
    metadata = render_source_metadata_insert_sql(
        SourceMetadataEvidenceRecord("run-1", "main.silver.orders", {"path": "s3://bucket/orders"}, now)
    )
    stream = render_stream_batch_insert_sql(
        StreamBatchEvidenceRecord("run-1", "main.silver.orders", "42", {"inputRows": 10}, now)
    )
    access = render_access_insert_sql(
        AccessEvidenceRecord("run-1", "main.silver.orders", "grant", "SUCCESS", {"principal": "analysts"}, now)
    )

    assert "ctrl_ingestion_quarantine" in quarantine
    assert "ctrl_ingestion_metadata" in metadata
    assert "ctrl_ingestion_streams" in stream
    assert "ctrl_ingestion_access" in access
