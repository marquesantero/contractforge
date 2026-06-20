from datetime import datetime, timezone

from contractforge_databricks.evidence import (
    EvidenceWriter,
    render_error_log_insert_sql,
    render_schema_change_log_insert_sqls,
    render_stream_child_run_metrics_sql,
    render_stream_finish_update_sql,
    render_stream_log_insert_sql,
)
from contractforge_databricks.evidence.helpers import utc_timestamp


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def test_render_error_log_insert_sql_redacts_stack_trace() -> None:
    sql = render_error_log_insert_sql(
        {
            "run_id": "run-1",
            "error_ts_utc": datetime(2026, 1, 1, 12, 0, 0),
            "error_date": "2026-01-01",
            "target": {"table": "main.silver.orders"},
            "mode": "scd1_upsert",
            "status": "FAILED",
            "error_type": "AnalysisException",
            "error_message": "password=raw-secret",
            "stack_trace": "Caused by: token=raw-token",
            "ctrl_schema_version": 1,
        }
    )

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_errors`" in sql
    assert "error_type" in sql
    assert "AnalysisException" in sql
    assert "raw-secret" not in sql
    assert "raw-token" not in sql
    assert "***REDACTED***" in sql


def test_render_schema_change_log_insert_sqls_from_diff_payload() -> None:
    statements = render_schema_change_log_insert_sqls(
        run_id="run-1",
        target_table="main.silver.orders",
        schema_changes={
            "added_columns": ["ingested_at"],
            "type_changes": [{"column": "amount", "source": "INT", "target": "BIGINT", "applied": False}],
        },
        source_schema={"ingested_at": "TIMESTAMP"},
        clock=lambda: datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
    )

    assert len(statements) == 2
    assert "ctrl_ingestion_schema_changes" in statements[0]
    assert "'add_column'" in statements[0]
    assert "'ingested_at'" in statements[0]
    assert "'TIMESTAMP'" in statements[0]
    assert "change_ts_utc" in statements[0]
    assert "changed_at_utc" in statements[0]
    assert "2026-02-03 04:05:06" in statements[0]
    assert "framework_version" in statements[0]
    assert "ctrl_schema_version" in statements[0]
    assert '"source_type":"TIMESTAMP"' in statements[0]
    assert "'amount'" in statements[1]
    assert "false" in statements[1]
    assert "payload_json" in statements[1]


def test_render_stream_log_insert_and_finish_update_sql() -> None:
    start = render_stream_log_insert_sql(
        {
            "stream_run_id": "stream-1",
            "target": {"table": "main.bronze.orders"},
            "trigger": "available_now",
            "checkpoint_location": "dbfs:/chk/orders",
            "status": "RUNNING",
            "started_at_utc": "2026-01-01 12:00:00",
            "ctrl_schema_version": 1,
        }
    )
    finish = render_stream_finish_update_sql(
        stream_run_id="stream-1",
        payload={
            "status": "SUCCESS",
            "ended_at_utc": "2026-01-01 12:05:00",
            "duration_seconds": 300,
            "batches_processed": 2,
            "total_rows_written": 10,
        },
    )

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_streams`" in start
    assert "'available_now'" in start
    assert finish is not None
    assert "UPDATE `main`.`ops`.`ctrl_ingestion_streams` SET" in finish
    assert "`total_rows_written` = 10" in finish
    assert "WHERE stream_run_id = 'stream-1'" in finish


def test_render_stream_log_insert_enriches_start_evidence() -> None:
    sql = render_stream_log_insert_sql(
        {"stream_run_id": "stream-1", "status": "RUNNING"},
        clock=lambda: datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
    )

    assert "started_at_utc" in sql
    assert "captured_at_utc" in sql
    assert "2026-02-03 04:05:06" in sql
    assert "framework_version" in sql
    assert "ctrl_schema_version" in sql
    assert "batches_processed" in sql
    assert "CAST('" in sql


def test_render_stream_child_run_metrics_sql() -> None:
    sql = render_stream_child_run_metrics_sql(stream_run_id="stream-1")

    assert "FROM `main`.`ops`.`ctrl_ingestion_runs`" in sql
    assert "parent_run_id = 'stream-1'" in sql
    assert "total_rows_quarantined" in sql


def test_evidence_writer_can_write_operational_logs() -> None:
    runner = FakeRunner()
    writer = EvidenceWriter(runner, clock=lambda: "2026-02-03 04:05:06")

    writer.write_error_log({"run_id": "run-1", "error_message": "failed"})
    writer.write_schema_change_log({"run_id": "run-1", "change_type": "add_column"})
    writer.write_stream_log({"stream_run_id": "stream-1", "status": "RUNNING"})
    writer.finish_stream_log(stream_run_id="stream-1", payload={"status": "SUCCESS"})

    assert len(runner.statements) == 4
    assert "ctrl_ingestion_errors" in runner.statements[0]
    assert "ctrl_ingestion_schema_changes" in runner.statements[1]
    assert "ctrl_ingestion_streams" in runner.statements[2]
    assert "2026-02-03 04:05:06" in runner.statements[2]
    assert runner.statements[3].startswith("UPDATE")


def test_utc_timestamp_uses_injected_clock() -> None:
    assert utc_timestamp(lambda: datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)) == "2026-02-03 04:05:06"
