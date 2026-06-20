from contractforge_databricks.state import (
    StateWriter,
    control_table_additive_migrations,
    render_acquire_lock_sql,
    render_control_metadata_current_sql,
    render_control_table_migrations_sql,
    render_create_state_tables_sql,
    render_find_idempotent_run_sql,
    render_find_idempotent_stream_sql,
    render_has_successful_run_sql,
    render_lock_status_sql,
    render_record_control_metadata_sql,
    render_release_lock_sql,
    render_select_previous_watermark_sql,
    render_upsert_state_sql,
)


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


class FailingReleaseRunner(FakeRunner):
    def sql(self, statement: str) -> None:
        super().sql(statement)
        if "UPDATE `main`.`ops`.`ctrl_ingestion_locks`" in statement:
            raise RuntimeError("lock table unavailable")


def test_render_create_state_tables_sql() -> None:
    sql = render_create_state_tables_sql(catalog="main", schema="ops")

    assert "CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_state`" in sql
    assert "CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_locks`" in sql


def test_render_control_table_migrations_sql() -> None:
    migrations = control_table_additive_migrations(catalog="main", schema="ops")
    sql = render_control_table_migrations_sql(catalog="main", schema="ops")

    assert "main.ops.ctrl_ingestion_runs" in migrations
    assert migrations["main.ops.ctrl_ingestion_runs"]["write_engine_selected"] == "STRING"
    assert migrations["main.ops.ctrl_ingestion_runs"]["write_started_at_utc"] == "TIMESTAMP"
    assert migrations["main.ops.ctrl_ingestion_runs"]["table_version_after"] == "STRING"
    assert migrations["main.ops.ctrl_ingestion_runs"]["parent_run_id"] == "STRING"
    assert migrations["main.ops.ctrl_ingestion_runs"]["source_system"] == "STRING"
    assert migrations["main.ops.ctrl_ingestion_runs"]["metrics_json"] == "STRING"
    assert migrations["main.ops.ctrl_ingestion_state"]["last_table_version"] == "STRING"
    assert migrations["main.ops.ctrl_ingestion_state"]["last_write_completed_at_utc"] == "TIMESTAMP"
    assert migrations["main.ops.ctrl_ingestion_errors"]["error_class"] == "STRING"
    assert migrations["main.ops.ctrl_ingestion_streams"]["batch_metrics_json"] == "STRING"
    assert migrations["main.ops.ctrl_ingestion_locks"]["released_at_utc"] == "TIMESTAMP"
    assert "ALTER TABLE `main`.`ops`.`ctrl_ingestion_runs` ADD COLUMNS" in sql
    assert "`write_engine_selected` STRING" in sql
    assert "`write_started_at_utc` TIMESTAMP" in sql
    assert "`last_table_version` STRING" in sql
    assert "`source_system` STRING" in sql
    assert "ALTER TABLE `main`.`ops`.`ctrl_ingestion_locks` ADD COLUMNS" in sql
    assert "`released_at_utc` TIMESTAMP" in sql


def test_render_acquire_and_release_lock_sql() -> None:
    acquire = render_acquire_lock_sql(target_table="main.silver.orders", run_id="run-1", owner="job", ttl_minutes=30)
    release = render_release_lock_sql(target_table="main.silver.orders", run_id="run-1")

    assert "MERGE INTO `main`.`ops`.`ctrl_ingestion_locks`" in acquire
    assert "INTERVAL 30 MINUTES" in acquire
    assert "UPDATE `main`.`ops`.`ctrl_ingestion_locks`" in release
    assert "status = 'RELEASED'" in release


def test_render_find_idempotent_run_sql() -> None:
    sql = render_find_idempotent_run_sql(
        target_table="main.silver.orders",
        idempotency_key="batch-42",
        status="SUCCESS",
    )

    assert "FROM `main`.`ops`.`ctrl_ingestion_runs`" in sql
    assert "idempotency_key = 'batch-42'" in sql
    assert "status = 'SUCCESS'" in sql
    assert "ORDER BY run_ts_utc DESC NULLS LAST" in sql


def test_render_idempotent_stream_and_successful_run_sql() -> None:
    stream = render_find_idempotent_stream_sql(
        target_table="main.bronze.orders",
        idempotency_key="stream-window-1",
        status="SUCCESS",
    )
    successful = render_has_successful_run_sql(
        target_table="main.silver.orders",
        idempotency_key="batch-42",
    )

    assert "FROM `main`.`ops`.`ctrl_ingestion_streams`" in stream
    assert "SELECT stream_run_id, status" in stream
    assert "ORDER BY started_at_utc DESC NULLS LAST" in stream
    assert "SELECT count(1) > 0 AS has_successful_run" in successful
    assert "AND status = 'SUCCESS'" in successful


def test_render_select_previous_watermark_sql() -> None:
    sql = render_select_previous_watermark_sql(
        target_table="main.silver.orders",
        state_table="ops.audit.ctrl_ingestion_state",
    )

    assert "SELECT watermark_value" in sql
    assert "FROM `ops`.`audit`.`ctrl_ingestion_state`" in sql
    assert "target_table = 'main.silver.orders'" in sql


def test_render_lock_status_and_control_metadata_sql() -> None:
    lock = render_lock_status_sql(target_table="main.silver.orders")
    current = render_control_metadata_current_sql(framework_version="1.2.3", ctrl_schema_version=4)
    record = render_record_control_metadata_sql(framework_version="1.2.3", ctrl_schema_version=4)

    assert "FROM `main`.`ops`.`ctrl_ingestion_locks`" in lock
    assert "target_table = 'main.silver.orders'" in lock
    assert "FROM `main`.`ops`.`ctrl_ingestion_metadata`" in current
    assert "framework_version = '1.2.3'" in current
    assert "MERGE INTO `main`.`ops`.`ctrl_ingestion_metadata`" in record
    assert "ctrl_schema_version" in record
    assert "UPDATE SET *" not in record
    assert "WHEN NOT MATCHED THEN INSERT (" in record


def test_render_upsert_state_sql() -> None:
    sql = render_upsert_state_sql(
        target_table="main.silver.orders",
        run_id="run-1",
        status="SUCCESS",
        rows_written=10,
        watermark_column="updated_at",
        watermark_value="2026-01-01T00:00:00Z",
    )

    assert "MERGE INTO `main`.`ops`.`ctrl_ingestion_state`" in sql
    assert "last_rows_written" in sql
    assert "'updated_at'" in sql


def test_state_writer_uses_runner() -> None:
    runner = FakeRunner()
    writer = StateWriter(runner)

    writer.acquire_lock(target_table="main.silver.orders", run_id="run-1")
    writer.release_lock(target_table="main.silver.orders", run_id="run-1")

    assert len(runner.statements) == 2
    assert "ctrl_ingestion_locks" in runner.statements[0]


def test_state_writer_release_lock_is_best_effort() -> None:
    runner = FailingReleaseRunner()
    writer = StateWriter(runner)

    writer.release_lock(target_table="main.silver.orders", run_id="run-1")

    assert len(runner.statements) == 1
    assert "ctrl_ingestion_locks" in runner.statements[0]


def test_state_writer_verifies_lock_when_query_one_is_available() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str) -> dict[str, object]:
        queries.append(statement)
        return {"run_id": "other-run", "status": "ACTIVE", "owner": "job-2"}

    writer = StateWriter(runner, query_one=query_one)

    try:
        writer.acquire_lock(target_table="main.silver.orders", run_id="run-1")
    except RuntimeError as exc:
        assert "Lock is busy" in str(exc)
    else:
        raise AssertionError("Expected busy lock to raise")

    assert "MERGE INTO `main`.`ops`.`ctrl_ingestion_locks`" in runner.statements[0]
    assert "FROM `main`.`ops`.`ctrl_ingestion_locks`" in queries[0]


def test_state_writer_records_control_metadata() -> None:
    runner = FakeRunner()
    writer = StateWriter(runner, catalog="ops", schema="audit")

    writer.record_control_metadata(framework_version="1.2.3", ctrl_schema_version=4)

    assert len(runner.statements) == 1
    assert "MERGE INTO `ops`.`audit`.`ctrl_ingestion_metadata`" in runner.statements[0]
