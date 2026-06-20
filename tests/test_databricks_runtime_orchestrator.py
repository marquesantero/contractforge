import pytest

from contractforge_core.errors import ContractForgeExecutionError
from contractforge_core.runtime import QuarantineReference
from contractforge_databricks.quality import QualityRuleResult
from contractforge_databricks.runtime import (
    DatabricksIngestOptions,
    DatabricksIngestionHooks,
    PreparedViewInput,
    ingest_databricks_contract,
)


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def _contract(mode: str = "scd0_append") -> dict[str, object]:
    contract: dict[str, object] = {
        "source": {"type": "table", "table": "main.raw.orders"},
        "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
        "mode": mode,
    }
    if mode == "scd1_upsert":
        contract["merge_keys"] = ["order_id"]
    if mode == "scd1_hash_diff":
        contract["hash_keys"] = ["order_id"]
    return contract


def test_ingest_databricks_contract_executes_append_and_records_state() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_schema={"order_id": "BIGINT", "amount": "DOUBLE"},
            rows_read=12,
            source_metadata={
                "source_type": "connector",
                "source_connector": "postgres",
                "source_provider": "jdbc",
                "source_path": "public.orders",
                "source_options": {"fetchsize": 1000},
                "source_auth": {"password": "***REDACTED***"},
            },
        ),
        options=DatabricksIngestOptions(run_id="run-1", runtime_metadata={"runtime_type": "serverless"}),
    )

    assert result["status"] == "SUCCESS"
    assert result["rows_read"] == 12
    assert result["rows_written"] == 12
    assert result["source_type"] == "connector"
    assert result["source_connector"] == "postgres"
    assert result["source_auth_json"] == {"password": "***REDACTED***"}
    assert result["write_engine_requested"] == "auto"
    assert result["write_engine_selected"] == "delta_append"
    assert result["write_engine_status"] == "native_databricks"
    assert result["write_engine"]["write_engine_selected"] == "delta_append"
    assert result["rows_effective"] == 12
    assert result["operation_metrics"] == result["operation_metrics_json"]
    assert result["write_started_at_utc"] is not None
    assert result["write_finished_at_utc"] is not None
    assert result["stage_durations"] == result["stage_durations_json"]
    assert set(result["stage_durations_json"]) >= {"schema", "preflight", "write", "maintenance", "governance"}
    assert result["ctrl_schema_version"] == 1
    assert any(
        statement.startswith("CREATE TABLE IF NOT EXISTS `main`.`bronze`.`orders`")
        for statement in runner.statements
    )
    assert any("INSERT INTO `main`.`bronze`.`orders`" in statement for statement in runner.statements)
    run_log_sql = next(statement for statement in runner.statements if "ctrl_ingestion_runs" in statement)
    assert "source_connector" in run_log_sql
    assert "postgres" in run_log_sql
    assert "raw-secret" not in run_log_sql
    metadata_sql = next(statement for statement in runner.statements if "ctrl_ingestion_metadata" in statement)
    assert "source_metadata_json" in metadata_sql
    assert "postgres" in metadata_sql
    assert "raw-secret" not in metadata_sql
    control_metadata_sql = next(
        statement for statement in runner.statements if "ctrl_ingestion_metadata" in statement and "component" in statement
    )
    assert "contractforge" in control_metadata_sql
    state_sql = next(statement for statement in runner.statements if "ctrl_ingestion_state" in statement)
    assert "MERGE INTO `main`.`ops`.`ctrl_ingestion_state`" in state_sql
    assert "CAST(NULL AS TIMESTAMP) AS last_success_at_utc" not in state_sql
    assert "CAST(NULL AS TIMESTAMP) AS last_write_completed_at_utc" not in state_sql


def test_ingest_databricks_contract_returns_applied_presets_metadata() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {**_contract(), "applied_presets": ["quality_quarantine"]},
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=3),
        options=DatabricksIngestOptions(
            run_id="run-1",
            runtime_metadata={"spark_version": "16.4", "notebook_name": "jobs/orders_ingest"},
        ),
    )

    assert result["applied_presets"] == ["quality_quarantine"]
    assert result["contract_metadata"]["applied_presets"] == ["quality_quarantine"]


def test_ingest_databricks_contract_maps_observability_metadata() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {
            **_contract(),
            "source": {"type": "table", "table": "main.raw.orders", "system": "crm"},
        },
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=3),
        options=DatabricksIngestOptions(
            run_id="run-1",
            schema="ops_prod",
            runtime_metadata={"notebook_name": "jobs/orders_ingest"},
        ),
    )

    assert result["runtime_entrypoint"] == "jobs/orders_ingest"
    assert result["source_system"] == "crm"
    assert any("`main`.`ops_prod`.`ctrl_ingestion_runs`" in statement for statement in runner.statements)


def test_ingest_databricks_contract_records_execution_hierarchy_metadata() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {
            **_contract(),
            "parent_run_id": "parent-1",
            "run_group_id": "group-1",
            "master_job_id": "job-1",
            "master_run_id": "master-1",
            "runtime_parameters": {"_contractforge_window_label": "day-1"},
        },
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=3),
        options=DatabricksIngestOptions(run_id="child-1"),
    )

    assert result["parent_run_id"] == "parent-1"
    assert result["run_group_id"] == "group-1"
    assert result["master_job_id"] == "job-1"
    assert result["master_run_id"] == "master-1"
    assert result["runtime_parameters_json"] == {"_contractforge_window_label": "day-1"}
    run_log_sql = next(statement for statement in runner.statements if "ctrl_ingestion_runs" in statement)
    state_sql = next(statement for statement in runner.statements if "ctrl_ingestion_state" in statement)
    assert "parent-1" in run_log_sql
    assert "group-1" in run_log_sql
    assert "parent-1" in state_sql
    assert "group-1" in state_sql


def test_ingest_databricks_rejects_source_system_root_alias() -> None:
    runner = FakeRunner()

    with pytest.raises(ValueError, match="source_system"):
        ingest_databricks_contract(
            {**_contract(), "source_system": "crm"},
            runner=runner,
            prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
            options=DatabricksIngestOptions(run_id="run-1"),
        )


def test_ingest_databricks_rejects_notebook_name_contract_alias() -> None:
    runner = FakeRunner()

    with pytest.raises(ValueError, match="notebook_name"):
        ingest_databricks_contract(
            {**_contract(), "notebook_name": "jobs/orders_ingest"},
            runner=runner,
            prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
            options=DatabricksIngestOptions(run_id="run-1"),
        )


def test_ingest_databricks_rejects_ctrl_schema_contract_alias() -> None:
    runner = FakeRunner()

    with pytest.raises(ValueError, match="ctrl_schema"):
        ingest_databricks_contract(
            {**_contract(), "ctrl_schema": "ops_from_contract"},
            runner=runner,
            prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
            options=DatabricksIngestOptions(run_id="run-1", schema="ops_from_options"),
        )


def test_ingest_databricks_contract_can_skip_table_setup() -> None:
    runner = FakeRunner()

    ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_schema={"order_id": "BIGINT", "amount": "DOUBLE"},
            rows_read=2,
        ),
        options=DatabricksIngestOptions(run_id="run-1", ensure_table=False),
    )

    assert not any(statement.startswith("CREATE TABLE IF NOT EXISTS") for statement in runner.statements)
    assert any("INSERT INTO `main`.`bronze`.`orders`" in statement for statement in runner.statements)


def test_ingest_databricks_contract_applies_additive_schema_sync() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {**_contract(), "schema_policy": "additive_only"},
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_schema={"order_id": "BIGINT", "amount": "DOUBLE"},
            rows_read=2,
        ),
        options=DatabricksIngestOptions(
            run_id="run-1",
            ensure_table=False,
            target_schema={"order_id": "BIGINT"},
        ),
    )

    assert result["schema_changes"]["added_columns"] == ["amount"]
    assert any("ADD COLUMNS (`amount` DOUBLE)" in statement for statement in runner.statements)
    assert any("ctrl_ingestion_schema_changes" in statement for statement in runner.statements)
    schema_change_sql = next(statement for statement in runner.statements if "ctrl_ingestion_schema_changes" in statement)
    assert "'DOUBLE'" in schema_change_sql
    assert "change_ts_utc" in schema_change_sql
    assert "changed_at_utc" in schema_change_sql
    assert "payload_json" in schema_change_sql
    assert any("INSERT INTO `main`.`bronze`.`orders`" in statement for statement in runner.statements)


def test_ingest_databricks_contract_marks_applied_type_widening() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {
            **_contract(),
            "schema_policy": "permissive",
            "extensions": {"databricks": {"allow_type_widening": True}},
        },
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_schema={"order_id": "BIGINT"},
            rows_read=2,
        ),
        options=DatabricksIngestOptions(
            run_id="run-1",
            ensure_table=False,
            target_schema={"order_id": "INT"},
        ),
    )

    assert result["schema_changes"]["type_changes"][0]["applied"] is True
    assert any("ALTER COLUMN `order_id` TYPE BIGINT" in statement for statement in runner.statements)
    assert any('"applied":true' in statement for statement in runner.statements if "ctrl_ingestion_schema_changes" in statement)


def test_ingest_databricks_contract_blocks_strict_schema_drift_after_evidence() -> None:
    runner = FakeRunner()

    with pytest.raises(ContractForgeExecutionError) as exc_info:
        ingest_databricks_contract(
            {**_contract(), "schema_policy": "strict"},
            runner=runner,
            prepared=PreparedViewInput(
                source_view="prepared_orders",
                source_schema={"order_id": "BIGINT", "amount": "DOUBLE"},
                rows_read=2,
            ),
            options=DatabricksIngestOptions(
                run_id="run-1",
                ensure_table=False,
                target_schema={"order_id": "BIGINT"},
            ),
        )

    assert exc_info.value.status == "FAILED"
    assert "Schema policy strict violation" in str(exc_info.value)
    assert any("ctrl_ingestion_errors" in statement for statement in runner.statements)
    assert not any("INSERT INTO `main`.`bronze`.`orders`" in statement for statement in runner.statements)


def test_ingest_databricks_contract_dry_run_previews_without_sql_side_effects() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {**_contract(), "schema_policy": "additive_only"},
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_schema={"order_id": "BIGINT", "amount": "DOUBLE"},
            rows_read=2,
        ),
        options=DatabricksIngestOptions(
            run_id="run-1",
            dry_run=True,
            target_schema={"order_id": "BIGINT"},
        ),
    )

    assert result["status"] == "DRY_RUN"
    assert result["rows_written"] == 0
    assert result["schema_changes"]["added_columns"] == ["amount"]
    assert runner.statements == []


def test_ingest_databricks_contract_accepts_run_id_factory() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", source_schema={"order_id": "BIGINT"}, rows_read=2),
        options=DatabricksIngestOptions(run_id_factory=lambda: "factory-run-1", dry_run=True),
    )

    assert result["run_id"] == "factory-run-1"


def test_ingest_databricks_contract_prefers_explicit_run_id_over_factory() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", source_schema={"order_id": "BIGINT"}, rows_read=2),
        options=DatabricksIngestOptions(
            run_id="explicit-run-1",
            run_id_factory=lambda: "factory-run-1",
            dry_run=True,
        ),
    )

    assert result["run_id"] == "explicit-run-1"


def test_ingest_databricks_contract_runs_post_write_optimize_when_requested() -> None:
    runner = FakeRunner()

    ingest_databricks_contract(
        {
            **_contract(),
            "extensions": {"databricks": {"optimize_after_write": True, "zorder_columns": ["order_id"]}},
        },
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", source_schema={"order_id": "BIGINT"}, rows_read=2),
        options=DatabricksIngestOptions(run_id="run-1", ensure_table=False),
    )

    insert_index = next(i for i, statement in enumerate(runner.statements) if "INSERT INTO `main`.`bronze`.`orders`" in statement)
    optimize_index = next(i for i, statement in enumerate(runner.statements) if statement.startswith("OPTIMIZE"))
    assert optimize_index > insert_index
    assert runner.statements[optimize_index] == "OPTIMIZE `main`.`bronze`.`orders` ZORDER BY (`order_id`)"


def test_ingest_databricks_contract_uses_delta_history_metrics_when_available() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        return {
            "version": 8,
            "operation": "WRITE",
            "operationMetrics": {"numOutputRows": "5"},
        }

    result = ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=5),
        options=DatabricksIngestOptions(
            run_id="run-1",
            runtime_metadata={"spark_version": "16.4", "notebook_name": "jobs/orders_ingest"},
        ),
        query_one=query_one,
    )

    assert queries == ["DESCRIBE HISTORY `main`.`bronze`.`orders` LIMIT 1"]
    assert result["rows_written"] == 5
    assert result["rows_inserted"] == 5
    assert result["table_version_after"] == "8"
    assert result["write_delta_version"] == 8
    assert result["operation_metrics_json"]["version"] == 8
    assert result["metrics_source"] == "mixed"
    state_sql = next(statement for statement in runner.statements if "ctrl_ingestion_state" in statement)
    assert "last_table_version" in state_sql
    assert "'8' AS last_table_version" in state_sql


def test_ingest_databricks_contract_collects_watermark_candidate() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        if statement.startswith("DESCRIBE HISTORY"):
            return None
        return {"watermark_value": '{"updated_at":{"type":"timestamp","value":"2026-01-01 00:00:00"}}'}

    result = ingest_databricks_contract(
        {**_contract(), "watermark_columns": ["updated_at"]},
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_schema={"order_id": "BIGINT", "updated_at": "timestamp"},
            rows_read=5,
        ),
        options=DatabricksIngestOptions(run_id="run-1"),
        query_one=query_one,
    )

    assert len(queries) == 3
    assert "MAX(`updated_at`)" in queries[1]
    assert "FROM `main`.`ops`.`ctrl_ingestion_state`" in queries[2]
    assert result["watermark_column"] == "updated_at"
    assert result["watermark_previous"] == '{"updated_at":{"type":"timestamp","value":"2026-01-01 00:00:00"}}'
    assert result["watermark_current"] == '{"updated_at":{"type":"timestamp","value":"2026-01-01 00:00:00"}}'
    state_sql = next(statement for statement in runner.statements if "ctrl_ingestion_state" in statement)
    assert "last_watermark_candidate" in state_sql
    assert "2026-01-01 00:00:00" in state_sql


def test_ingest_databricks_contract_writes_runtime_explain_and_openlineage() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        if statement.startswith("DESCRIBE HISTORY"):
            return {"version": 9, "operation": "WRITE", "operationMetrics": {"numOutputRows": "4"}}
        if statement.startswith("EXPLAIN"):
            return {"plan_text": "== Physical Plan ==\nScan prepared_orders"}
        return None

    result = ingest_databricks_contract(
        {
            **_contract(),
            "extensions": {"databricks": {"explain_mode": True, "openlineage_enabled": True}},
            "parent_run_id": "parent-1",
        },
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_schema={"order_id": "BIGINT"},
            rows_read=4,
            source_name="main.raw.orders",
        ),
        options=DatabricksIngestOptions(
            run_id="run-1",
            runtime_metadata={"spark_version": "16.4", "notebook_name": "jobs/orders_ingest"},
        ),
        query_one=query_one,
    )

    assert any(statement.startswith("EXPLAIN FORMATTED") for statement in queries)
    assert result["explain_captured"] is True
    assert result["openlineage_event_emitted"] is True
    assert any("ctrl_ingestion_explain" in statement for statement in runner.statements)
    assert any("ctrl_ingestion_lineage" in statement for statement in runner.statements)
    lineage_sql = next(statement for statement in runner.statements if "ctrl_ingestion_lineage" in statement)
    assert '"deltaVersionAfter":9' in lineage_sql
    assert '"parent"' in lineage_sql
    assert '"runId":"parent-1"' in lineage_sql
    assert '"version":"16.4"' in lineage_sql
    assert '"url":"jobs/orders_ingest"' in lineage_sql


def test_ingest_databricks_contract_records_operations_and_applies_annotations() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {
            **_contract(),
            "annotations": {"table": {"description": "Bronze orders"}},
            "operations": {"operations": {"criticality": "high", "owners": ["data-eng"]}},
        },
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
        options=DatabricksIngestOptions(run_id="run-1"),
    )

    assert result["annotations_status"] == "SUCCESS"
    assert result["annotations_result_json"]["applied"] == 1
    assert result["operations_json"]["record_result"]["status"] == "RECORDED"
    assert any("ctrl_ingestion_operations" in statement for statement in runner.statements)
    assert any(statement.startswith("COMMENT ON TABLE") for statement in runner.statements)


def test_ingest_databricks_contract_fails_when_annotation_fail_policy_fails() -> None:
    class FailingCommentRunner(FakeRunner):
        def sql(self, statement: str) -> None:
            super().sql(statement)
            if statement.startswith("COMMENT ON TABLE"):
                raise RuntimeError("comment rejected")

    runner = FailingCommentRunner()

    with pytest.raises(ContractForgeExecutionError) as exc_info:
        ingest_databricks_contract(
            {**_contract(), "annotations": {"policy": "fail", "table": {"description": "Bronze orders"}}},
            runner=runner,
            prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
            options=DatabricksIngestOptions(run_id="run-1"),
        )

    assert exc_info.value.status == "FAILED"
    assert "Databricks annotations failed" in str(exc_info.value)
    assert any("ctrl_ingestion_errors" in statement for statement in runner.statements)


def test_ingest_databricks_contract_dispatches_scd1_merge() -> None:
    runner = FakeRunner()

    ingest_databricks_contract(
        _contract("scd1_upsert"),
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_columns=("order_id", "amount"),
            source_schema={"order_id": "BIGINT", "amount": "DOUBLE"},
            rows_read=3,
        ),
        options=DatabricksIngestOptions(run_id="run-1"),
    )

    assert any("CREATE TABLE IF NOT EXISTS `main`.`bronze`.`orders`" in statement for statement in runner.statements)
    assert any("MERGE INTO `main`.`bronze`.`orders`" in statement for statement in runner.statements)
    assert any("t.`order_id` <=> s.`order_id`" in statement for statement in runner.statements)


def test_ingest_databricks_contract_blocks_duplicate_merge_keys_before_merge() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        if "all_keys_null_rows" in statement:
            return {"all_keys_null_rows": 0}
        if "duplicate_key_groups" in statement:
            return {"duplicate_key_groups": 1, "duplicate_rows": 2}
        return None

    with pytest.raises(ContractForgeExecutionError) as exc_info:
        ingest_databricks_contract(
            _contract("scd1_upsert"),
            runner=runner,
            prepared=PreparedViewInput(
                source_view="prepared_orders",
                source_columns=("order_id", "amount"),
                rows_read=2,
            ),
            options=DatabricksIngestOptions(run_id="run-1", ensure_table=False),
            query_one=query_one,
        )

    assert "duplicate source rows" in str(exc_info.value)
    assert any("all_keys_null_rows" in statement for statement in queries)
    assert any("duplicate_key_groups" in statement for statement in queries)
    assert any("ctrl_ingestion_errors" in statement for statement in runner.statements)
    assert not any(statement.startswith("MERGE INTO `main`.`bronze`.`orders`") for statement in runner.statements)


def test_ingest_databricks_contract_skips_duplicate_query_when_unique_key_already_passed() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        if "all_keys_null_rows" in statement:
            return {"all_keys_null_rows": 0}
        if statement.startswith("DESCRIBE HISTORY"):
            return None
        return None

    ingest_databricks_contract(
        {**_contract("scd1_upsert"), "quality_rules": {"unique_key": ["order_id"]}},
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_columns=("order_id", "amount"),
            rows_read=2,
        ),
        options=DatabricksIngestOptions(run_id="run-1", ensure_table=False),
        query_one=query_one,
        quality_results=(QualityRuleResult("unique_key", "PASSED", failed_count=0, severity="abort"),),
    )

    assert any("all_keys_null_rows" in statement for statement in queries)
    assert not any("duplicate_key_groups" in statement for statement in queries)
    assert any(statement.startswith("MERGE INTO `main`.`bronze`.`orders`") for statement in runner.statements)


def test_ingest_databricks_contract_skips_successful_idempotency_key() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=12),
        options=DatabricksIngestOptions(
            run_id="run-2",
            idempotency_key="orders:batch:1",
            idempotency_policy="skip_if_success",
        ),
        query_one=lambda statement: {"run_id": "run-1", "status": "SUCCESS"},
    )

    assert result["status"] == "SKIPPED"
    assert result["skip_reason"] == "idempotency_key_already_succeeded"
    assert not any("INSERT INTO `main`.`bronze`.`orders`" in statement for statement in runner.statements)
    assert any("ctrl_ingestion_runs" in statement for statement in runner.statements)


def test_ingest_databricks_contract_uses_contract_idempotency_when_options_do_not_override() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        return {"run_id": "run-previous", "status": "SUCCESS"}

    result = ingest_databricks_contract(
        {**_contract(), "idempotency_key": "orders:batch:1", "idempotency_policy": "skip_if_success"},
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=12),
        options=DatabricksIngestOptions(run_id="run-2"),
        query_one=query_one,
    )

    assert result["status"] == "SKIPPED"
    assert result["idempotency_key"] == "orders:batch:1"
    assert "orders:batch:1" in queries[0]


def test_ingest_databricks_contract_uses_databricks_lock_extension() -> None:
    runner = FakeRunner()

    ingest_databricks_contract(
        {**_contract(), "extensions": {"databricks": {"lock_enabled": True}}},
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
        options=DatabricksIngestOptions(run_id="run-1"),
    )

    assert "MERGE INTO `main`.`ops`.`ctrl_ingestion_locks`" in runner.statements[0]
    assert "UPDATE `main`.`ops`.`ctrl_ingestion_locks`" in runner.statements[-1]


def test_ingest_databricks_contract_retries_delta_concurrency_write() -> None:
    class FlakyInsertRunner(FakeRunner):
        def __init__(self) -> None:
            super().__init__()
            self.insert_attempts = 0

        def sql(self, statement: str) -> None:
            super().sql(statement)
            if "INSERT INTO `main`.`bronze`.`orders`" in statement:
                self.insert_attempts += 1
                if self.insert_attempts == 1:
                    raise RuntimeError("DELTA_CONCURRENT_APPEND conflict")

    runner = FlakyInsertRunner()

    result = ingest_databricks_contract(
        {**_contract(), "retry_attempts": 2, "retry_backoff_seconds": 0},
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
        options=DatabricksIngestOptions(run_id="run-1"),
    )

    assert result["status"] == "SUCCESS"
    assert runner.insert_attempts == 2


def test_ingest_databricks_contract_scopes_scd1_merge_by_partition_values() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        if "collect_set(`dt`)" in statement:
            return {"partition_values": ["2026-01-01", "2026-01-02"]}
        return None

    ingest_databricks_contract(
        {
            **_contract("scd1_upsert"),
            "extensions": {"databricks": {"merge_strategy": "delta_by_partition", "merge_partition_column": "dt"}},
        },
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_columns=("order_id", "amount", "dt"),
            rows_read=2,
        ),
        options=DatabricksIngestOptions(run_id="run-1", ensure_table=False),
        query_one=query_one,
    )

    assert "SELECT collect_set(`dt`) AS partition_values FROM `prepared_orders`" in queries
    merge_sql = next(statement for statement in runner.statements if statement.startswith("MERGE INTO `main`.`bronze`.`orders`"))
    assert "AND t.`dt` IN ('2026-01-01', '2026-01-02')" in merge_sql


def test_ingest_databricks_contract_passes_target_schema_to_hash_diff_latest_selection() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        _contract("scd1_hash_diff"),
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_columns=("order_id", "amount", "row_hash"),
            rows_read=2,
        ),
        options=DatabricksIngestOptions(
            run_id="run-1",
            ensure_table=False,
            target_schema={"order_id": "BIGINT", "row_hash": "STRING", "ingestion_sequence": "BIGINT"},
        ),
    )

    assert result["status"] == "SUCCESS"
    insert_sql = next(statement for statement in runner.statements if statement.startswith("INSERT INTO `main`.`bronze`.`orders`"))
    assert "ORDER BY ingestion_sequence DESC NULLS LAST" in insert_sql


def test_ingest_databricks_contract_replaces_complete_partitions() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        if "all_keys_null_rows" in statement:
            return {"all_keys_null_rows": 0}
        if "duplicate_key_groups" in statement:
            return {"duplicate_key_groups": 0, "duplicate_rows": 0}
        if "collect_set(`dt`)" in statement:
            return {"partition_values": ["2026-01-01", "2026-01-02"]}
        return None

    result = ingest_databricks_contract(
        {
            **_contract("scd1_upsert"),
            "extensions": {
                "databricks": {
                    "merge_strategy": "replace_partitions",
                    "merge_partition_column": "dt",
                    "partition_column": "dt",
                    "replace_partitions_source_complete": True,
                }
            },
        },
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            source_columns=("order_id", "amount", "dt"),
            rows_read=2,
        ),
        options=DatabricksIngestOptions(run_id="run-1", ensure_table=False),
        query_one=query_one,
    )

    assert result["status"] == "SUCCESS"
    replace_sql = next(statement for statement in runner.statements if statement.startswith("INSERT INTO TABLE"))
    assert "REPLACE WHERE `dt` IN ('2026-01-01', '2026-01-02')" in replace_sql
    assert "SELECT * FROM `prepared_orders`" in replace_sql
    assert not any(statement.startswith("MERGE INTO `main`.`bronze`.`orders`") for statement in runner.statements)


def test_ingest_databricks_contract_rejects_replace_partitions_without_complete_source() -> None:
    runner = FakeRunner()

    with pytest.raises(ContractForgeExecutionError) as exc_info:
        ingest_databricks_contract(
            {
                **_contract("scd1_upsert"),
                "extensions": {
                    "databricks": {"merge_strategy": "replace_partitions", "merge_partition_column": "dt"}
                },
            },
            runner=runner,
            prepared=PreparedViewInput(
                source_view="prepared_orders",
                source_columns=("order_id", "amount", "dt"),
                rows_read=2,
            ),
            options=DatabricksIngestOptions(run_id="run-1", ensure_table=False),
            query_one=lambda statement: None,
        )

    assert "replace_partitions_source_complete=true" in str(exc_info.value)
    assert any("ctrl_ingestion_errors" in statement for statement in runner.statements)
    assert not any(statement.startswith("INSERT INTO TABLE") for statement in runner.statements)


def test_ingest_databricks_contract_records_quality_failure() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=12),
        options=DatabricksIngestOptions(run_id="run-1", quality_action="fail", raise_on_failure=False),
        quality_results=(QualityRuleResult("not_null_order_id", "FAILED", failed_count=2, severity="abort"),),
    )

    assert result["status"] == "FAILED"
    assert result["quality_status"] == "FAILED"
    assert "Quality gates failed" in result["error_message"]
    assert any("ctrl_ingestion_errors" in statement for statement in runner.statements)
    assert any("ctrl_ingestion_quality" in statement for statement in runner.statements)
    assert any("not_null_order_id" in statement for statement in runner.statements)
    assert not any("INSERT INTO `main`.`bronze`.`orders`" in statement for statement in runner.statements)


def test_ingest_databricks_contract_uses_contract_on_quality_fail_policy() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {**_contract(), "on_quality_fail": "warn"},
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=12),
        options=DatabricksIngestOptions(run_id="run-1"),
        quality_results=(QualityRuleResult("not_null_order_id", "FAILED", failed_count=2, severity="abort"),),
    )

    assert result["status"] == "SUCCESS"
    assert result["quality_status"] == "FAILED"
    assert any("INSERT INTO `main`.`bronze`.`orders`" in statement for statement in runner.statements)
    assert any("ctrl_ingestion_quality" in statement for statement in runner.statements)


def test_ingest_databricks_contract_persists_quarantine_references() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {**_contract(), "on_quality_fail": "warn"},
        runner=runner,
        prepared=PreparedViewInput(
            source_view="prepared_orders",
            rows_read=12,
            rows_quarantined=1,
            quarantine_records=(
                QuarantineReference(
                    "dbfs:/quarantine/orders/run-1/part-000.json",
                    "quality_gate",
                    "not_null_order_id",
                ),
            ),
        ),
        options=DatabricksIngestOptions(run_id="run-1"),
        quality_results=(
            QualityRuleResult("not_null_order_id", "FAILED", failed_count=1, severity="quarantine"),
        ),
    )

    assert result["rows_quarantined"] == 1
    quarantine_sql = next(statement for statement in runner.statements if "ctrl_ingestion_quarantine" in statement)
    assert "dbfs:/quarantine/orders/run-1/part-000.json" in quarantine_sql
    assert "not_null_order_id: quality_gate" in quarantine_sql


def test_ingest_databricks_contract_reports_quarantined_status_under_quarantine_policy() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {**_contract(), "on_quality_fail": "quarantine"},
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=10, rows_quarantined=2),
        options=DatabricksIngestOptions(run_id="run-1"),
        quality_results=(
            QualityRuleResult("non_negative_amount", "FAILED", failed_count=2, severity="quarantine"),
        ),
    )

    assert result["status"] == "SUCCESS"
    assert result["quality_status"] == "QUARANTINED"


def test_ingest_databricks_contract_keeps_failed_status_when_policy_is_fail() -> None:
    runner = FakeRunner()

    result = ingest_databricks_contract(
        {**_contract(), "on_quality_fail": "fail"},
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=10),
        options=DatabricksIngestOptions(run_id="run-1", raise_on_failure=False),
        quality_results=(
            QualityRuleResult("non_negative_amount", "FAILED", failed_count=2, severity="quarantine"),
        ),
    )

    assert result["status"] == "FAILED"
    assert result["quality_status"] == "FAILED"


def test_ingest_databricks_contract_acquires_and_releases_lock() -> None:
    runner = FakeRunner()

    ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
        options=DatabricksIngestOptions(run_id="run-1", lock_enabled=True, lock_owner="job-1"),
    )

    assert "MERGE INTO `main`.`ops`.`ctrl_ingestion_locks`" in runner.statements[0]
    assert "UPDATE `main`.`ops`.`ctrl_ingestion_locks`" in runner.statements[-1]


def test_ingest_databricks_contract_fails_when_lock_readback_is_busy() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        if "ctrl_ingestion_locks" in statement:
            return {"run_id": "other-run", "status": "ACTIVE"}
        return None

    result = ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
        options=DatabricksIngestOptions(run_id="run-1", lock_enabled=True, lock_owner="job-1", raise_on_failure=False),
        query_one=query_one,
    )

    assert result["status"] == "FAILED"
    assert "Lock is busy" in result["error_message"]
    assert any("FROM `main`.`ops`.`ctrl_ingestion_locks`" in statement for statement in queries)


def test_ingest_databricks_contract_runs_prepared_runtime_hooks() -> None:
    runner = FakeRunner()
    events: list[str] = []

    def after_prepare(contract, prepared):
        events.append(f"after_prepare:{prepared.source_view}")
        return PreparedViewInput(source_view="prepared_orders_hooked", source_columns=prepared.source_columns, rows_read=5)

    def before_write(contract, prepared):
        events.append(f"before_write:{prepared.source_view}")
        return None

    def after_write(contract, prepared, outcome):
        events.append(f"after_write:{outcome.operation if outcome else 'none'}")

    def after_finalize(contract, result):
        events.append(f"after_finalize:{result['status']}")

    result = ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=12),
        options=DatabricksIngestOptions(
            run_id="run-1",
            hooks=DatabricksIngestionHooks(
                after_prepare=after_prepare,
                before_write=before_write,
                after_write=after_write,
                after_finalize=after_finalize,
            ),
        ),
    )

    assert result["status"] == "SUCCESS"
    assert result["rows_read"] == 5
    assert events == [
        "after_prepare:prepared_orders",
        "before_write:prepared_orders_hooked",
        "after_write:delta_append",
        "after_finalize:SUCCESS",
    ]
    assert any("prepared_orders_hooked" in statement for statement in runner.statements)


def test_ingest_databricks_contract_accepts_hooks_from_adapter_extension_field() -> None:
    runner = FakeRunner()
    events: list[str] = []

    def after_finalize(contract, result):
        events.append(f"after_finalize:{result['status']}")

    result = ingest_databricks_contract(
        {
            **_contract(),
            "extensions": {"databricks": {"hooks": DatabricksIngestionHooks(after_finalize=after_finalize)}},
        },
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
        options=DatabricksIngestOptions(run_id="run-1"),
    )

    assert result["status"] == "SUCCESS"
    assert events == ["after_finalize:SUCCESS"]


def test_ingest_databricks_contract_rejects_invalid_hooks_extension() -> None:
    runner = FakeRunner()

    with pytest.raises(ValueError, match="extensions.databricks.hooks must be DatabricksIngestionHooks"):
        ingest_databricks_contract(
            {**_contract(), "extensions": {"databricks": {"hooks": object()}}},
            runner=runner,
            prepared=PreparedViewInput(source_view="prepared_orders", rows_read=1),
            options=DatabricksIngestOptions(run_id="run-1", raise_on_failure=False),
        )


def test_databricks_ingestion_hooks_reject_non_callable_fields() -> None:
    with pytest.raises(ValueError, match="after_prepare must be callable"):
        DatabricksIngestionHooks(after_prepare="not-callable")  # type: ignore[arg-type]


def test_ingest_databricks_contract_records_hook_failure() -> None:
    runner = FakeRunner()

    def before_write(contract, prepared):
        raise RuntimeError("hook rejected write token=raw-token")

    result = ingest_databricks_contract(
        _contract(),
        runner=runner,
        prepared=PreparedViewInput(source_view="prepared_orders", rows_read=12),
        options=DatabricksIngestOptions(
            run_id="run-1",
            hooks=DatabricksIngestionHooks(before_write=before_write),
            raise_on_failure=False,
            runtime_metadata={"runtime_type": "serverless", "spark_version": "15.4"},
        ),
    )

    assert result["status"] == "FAILED"
    assert result["error_message"] == "hook rejected write token=***REDACTED***"
    error_sql = next(statement for statement in runner.statements if "ctrl_ingestion_errors" in statement)
    assert "error_class" in error_sql
    assert "RuntimeError" in error_sql
    assert "occurred_at_utc" in error_sql
    assert "serverless" in error_sql
    assert "15.4" in error_sql
    assert "raw-token" not in error_sql


def test_ingest_databricks_contract_raises_after_failure_evidence_by_default() -> None:
    runner = FakeRunner()

    with pytest.raises(ContractForgeExecutionError) as exc_info:
        ingest_databricks_contract(
            _contract(),
            runner=runner,
            prepared=PreparedViewInput(source_view="prepared_orders", rows_read=12),
            options=DatabricksIngestOptions(run_id="run-1", quality_action="fail"),
            quality_results=(QualityRuleResult("not_null_order_id", "FAILED", failed_count=2, severity="abort"),),
        )

    assert exc_info.value.status == "FAILED"
    assert exc_info.value.run_id == "run-1"
    assert "Quality gates failed" in str(exc_info.value)
    assert any("ctrl_ingestion_errors" in statement for statement in runner.statements)
    assert any("ctrl_ingestion_runs" in statement for statement in runner.statements)
