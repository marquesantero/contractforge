from __future__ import annotations

import json
import sys
import types

from contractforge_databricks.runtime import (
    DatabricksIngestOptions,
    apply_databricks_access_bundle,
    apply_databricks_annotations_bundle,
    apply_databricks_governance_bundle,
    ingest_databricks_bundle,
)
from contractforge_databricks.runtime.control_tables import ensure_control_tables


class FakeType:
    def __init__(self, name: str) -> None:
        self.name = name

    def simpleString(self) -> str:
        return self.name


class FakeField:
    def __init__(self, name: str, data_type: str) -> None:
        self.name = name
        self.dataType = FakeType(data_type)


class FakeSchema:
    def __init__(self) -> None:
        self.fields = [FakeField("order_id", "BIGINT"), FakeField("amount", "DOUBLE")]


class FakeDataFrame:
    columns = ["order_id", "amount"]

    def __init__(self) -> None:
        self.schema = FakeSchema()
        self.views: list[str] = []

    def createOrReplaceTempView(self, name: str) -> None:
        self.views.append(name)

    def where(self, condition: object) -> "FakeDataFrame":
        return self

    def count(self) -> int:
        return 3


class FakeQuery:
    def awaitTermination(self) -> None:
        return None


class FakeWriteStream:
    def __init__(self, batch_df: FakeDataFrame) -> None:
        self.batch_df = batch_df
        self.options: dict[str, str] = {}
        self.trigger_options: dict[str, object] = {}

    def foreachBatch(self, callback):
        self.callback = callback
        return self

    def option(self, key: str, value: str):
        self.options[key] = value
        return self

    def trigger(self, **kwargs):
        self.trigger_options.update(kwargs)
        return self

    def start(self):
        self.callback(self.batch_df, 1)
        return FakeQuery()


class FakeStreamDataFrame(FakeDataFrame):
    def __init__(self) -> None:
        super().__init__()
        self.writeStream = FakeWriteStream(self)


class FakeStreamReader:
    def __init__(self, stream_df: FakeStreamDataFrame) -> None:
        self.stream_df = stream_df
        self.options: dict[str, str] = {}
        self.source_format: str | None = None
        self.path: str | None = None

    def format(self, value: str):
        self.source_format = value
        return self

    def option(self, key: str, value: str):
        self.options[key] = value
        return self

    def load(self, path: str | None = None):
        self.path = path
        return self.stream_df


class FakeSpark:
    def __init__(self) -> None:
        self.table_calls: list[str] = []
        self.missing_tables: set[str] = set()
        self.table_df = FakeDataFrame()
        self.stream_df = FakeStreamDataFrame()
        self.readStream = FakeStreamReader(self.stream_df)
        self.catalog = FakeCatalog()

    def table(self, name: str) -> FakeDataFrame:
        self.table_calls.append(name)
        if name in self.missing_tables:
            raise RuntimeError(f"table not found: {name}")
        return self.table_df


class FakeCatalog:
    def __init__(self) -> None:
        self.cached: list[str] = []
        self.uncached: list[str] = []

    def cacheTable(self, name: str) -> None:
        self.cached.append(name)

    def uncacheTable(self, name: str) -> None:
        self.uncached.append(name)


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def test_ensure_control_tables_renders_core_control_tables() -> None:
    runner = FakeRunner()

    ensure_control_tables(runner=runner, catalog="main", schema="ops")

    assert runner.statements[0] == "CREATE SCHEMA IF NOT EXISTS `main`.`ops`"
    assert any("CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_runs`" in statement for statement in runner.statements)
    assert any("CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_state`" in statement for statement in runner.statements)
    assert any("source_system STRING" in statement for statement in runner.statements)


def test_ingest_databricks_bundle_loads_split_contract_and_executes_runtime(tmp_path) -> None:
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.json").write_text(
        json.dumps(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "orders.annotations.json").write_text(
        json.dumps({"target": {"catalog": "main", "schema": "bronze", "table": "orders"}, "table": {"description": "Orders"}}),
        encoding="utf-8",
    )
    spark = FakeSpark()
    runner = FakeRunner()

    result = ingest_databricks_bundle(
        base,
        spark=spark,
        runner=runner,
        options=DatabricksIngestOptions(run_id="run-1", ensure_table=False),
        collect_metrics=True,
    )

    assert result["status"] == "SUCCESS"
    assert result["rows_read"] == 3
    assert spark.table_calls == ["main.raw.orders"]
    assert spark.table_df.views == ["cf_source_main_bronze_orders"]
    assert any("INSERT INTO `main`.`bronze`.`orders`" in statement for statement in runner.statements)
    assert any(statement.startswith("COMMENT ON TABLE") for statement in runner.statements)


def test_ingest_databricks_bundle_caches_source_view_when_extension_requests_it(tmp_path) -> None:
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.json").write_text(
        json.dumps(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "extensions": {"databricks": {"cache_source": True}},
            }
        ),
        encoding="utf-8",
    )
    spark = FakeSpark()

    result = ingest_databricks_bundle(
        base,
        spark=spark,
        runner=FakeRunner(),
        options=DatabricksIngestOptions(run_id="run-cache", ensure_table=False),
        collect_metrics=True,
    )

    assert result["status"] == "SUCCESS"
    assert spark.catalog.cached == ["cf_source_main_bronze_orders"]
    assert spark.catalog.uncached == ["cf_source_main_bronze_orders"]


def test_ingest_databricks_bundle_evaluates_declared_quality_rules(tmp_path, monkeypatch) -> None:
    from contractforge_core.quality import QualityRuleResult
    from contractforge_databricks.runtime import quality_quarantine

    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.json").write_text(
        json.dumps(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "quality_rules": {"required_columns": ["order_id"], "min_rows": 1},
            }
        ),
        encoding="utf-8",
    )
    quality_calls = []

    def fake_evaluate_quality(df: FakeDataFrame, contract: object):
        quality_calls.append((df, contract))
        return "PASSED", (QualityRuleResult("min_rows", "PASSED", severity="abort"),), df, df, 0

    monkeypatch.setattr(quality_quarantine, "evaluate_quality", fake_evaluate_quality)
    spark = FakeSpark()
    runner = FakeRunner()

    result = ingest_databricks_bundle(
        base,
        spark=spark,
        runner=runner,
        options=DatabricksIngestOptions(run_id="run-quality", ensure_table=False),
        collect_metrics=True,
    )

    assert result["quality_status"] == "PASSED"
    assert len(quality_calls) == 1
    assert any("ctrl_ingestion_quality" in statement for statement in runner.statements)


def test_ingest_databricks_bundle_persists_declared_quality_quarantine_rows(tmp_path, monkeypatch) -> None:
    from contractforge_core.quality import QualityRuleResult
    from contractforge_databricks.runtime import quality_quarantine

    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.json").write_text(
        json.dumps(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "on_quality_fail": "quarantine",
                "quality_rules": {"not_null": ["order_id"]},
            }
        ),
        encoding="utf-8",
    )
    persisted = []

    def fake_evaluate_quality(df: FakeDataFrame, contract: object):
        return (
            "FAILED",
            (QualityRuleResult("order_id_not_null", "FAILED", failed_count=1, severity="quarantine"),),
            df,
            df,
            1,
        )

    def fake_persist(quarantined_df, **kwargs):
        persisted.append(kwargs)

    monkeypatch.setattr(quality_quarantine, "evaluate_quality", fake_evaluate_quality)
    monkeypatch.setattr(quality_quarantine, "persist_quality_quarantine_rows", fake_persist)

    result = ingest_databricks_bundle(
        base,
        spark=FakeSpark(),
        runner=FakeRunner(),
        options=DatabricksIngestOptions(run_id="run-quality-quarantine", ensure_table=False),
        collect_metrics=True,
    )

    assert result["quality_status"] == "QUARANTINED"
    assert result["rows_quarantined"] == 1
    assert persisted == [
        {
            "run_id": "run-quality-quarantine",
            "target_table": "main.bronze.orders",
            "quality_results": (QualityRuleResult("order_id_not_null", "FAILED", failed_count=1, severity="quarantine"),),
            "catalog": "main",
            "schema": "ops",
        }
    ]


def test_ingest_databricks_bundle_executes_windowed_child_runs(tmp_path, monkeypatch) -> None:
    _install_fake_pyspark(monkeypatch)
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.json").write_text(
        json.dumps(
            {
                "source": {"type": "table", "table": "main.raw.orders", "system": "erp"},
                "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "filter_expression": "amount > 0",
                "idempotency_key": "orders-load",
                "execution": {
                    "window": {
                        "column": "event_ts",
                        "start": "2026-01-01 00:00:00",
                        "end": "2026-01-03 00:00:00",
                        "every": "1 day",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    spark = FakeSpark()
    runner = FakeRunner()

    result = ingest_databricks_bundle(
        base,
        spark=spark,
        runner=runner,
        options=DatabricksIngestOptions(run_id="parent-1", ensure_table=False),
        collect_metrics=True,
    )

    assert result["status"] == "SUCCESS"
    assert result["run_id"] == "parent-1"
    assert result["windows_total"] == 2
    assert result["windows_processed"] == 2
    assert result["rows_read"] == 6
    assert spark.table_calls == ["main.raw.orders", "main.raw.orders"]
    assert spark.table_df.views == ["cf_source_main_bronze_orders_0001", "cf_source_main_bronze_orders_0002"]
    assert all(item["parent_run_id"] == "parent-1" for item in result["window_results"])
    assert all(item["source_system"] == "erp" for item in result["window_results"])
    run_logs = [
        statement
        for statement in runner.statements
        if "ctrl_ingestion_runs" in statement and statement.startswith("INSERT INTO")
    ]
    assert len(run_logs) == 2
    assert all("parent-1" in statement for statement in run_logs)
    assert all("orders-load:window:" in statement for statement in run_logs)


def test_ingest_databricks_bundle_routes_available_now_to_stream_runtime(tmp_path) -> None:
    base = tmp_path / "orders"
    (tmp_path / "orders.ingestion.json").write_text(
        json.dumps(
            {
                "source": {
                    "type": "incremental_files",
                    "path": "s3://bucket/landing/orders",
                    "format": "json",
                    "trigger": "available_now",
                    "progress_location": "s3://bucket/_checkpoints/orders",
                },
                "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "idempotency_key": "orders-stream",
            }
        ),
        encoding="utf-8",
    )
    spark = FakeSpark()
    spark.missing_tables.add("main.bronze.orders")
    runner = FakeRunner()

    result = ingest_databricks_bundle(
        base,
        spark=spark,
        runner=runner,
        options=DatabricksIngestOptions(run_id="stream-1"),
        collect_metrics=True,
    )

    assert result["status"] == "SUCCESS"
    assert result["batches_processed"] == 1
    assert result["total_rows_read"] == 3
    assert spark.readStream.source_format == "cloudFiles"
    assert spark.readStream.path == "s3://bucket/landing/orders"
    assert spark.stream_df.writeStream.options["checkpointLocation"] == "s3://bucket/_checkpoints/orders"
    assert spark.stream_df.writeStream.trigger_options == {"availableNow": True}
    assert "cf_stream_batch_stream_1_1" in spark.table_calls
    run_logs = [
        statement
        for statement in runner.statements
        if "ctrl_ingestion_runs" in statement and statement.startswith("INSERT INTO")
    ]
    assert len(run_logs) == 1
    assert "stream-1:batch:1" in run_logs[0]
    assert "stream-1" in run_logs[0]
    assert any(
        statement.startswith("CREATE TABLE IF NOT EXISTS `main`.`bronze`.`orders`")
        for statement in runner.statements
    )
    assert any("ctrl_ingestion_streams" in statement and "stream-1" in statement for statement in runner.statements)


def test_spark_target_schema_normalizes_databricks_types() -> None:
    from contractforge_databricks.runtime.spark_defaults import spark_target_schema

    spark = FakeSpark()

    assert spark_target_schema(spark, "main.bronze.orders") == {"order_id": "bigint", "amount": "double"}


def test_apply_databricks_governance_bundle_executes_split_sections(tmp_path) -> None:
    base = tmp_path / "customers"
    target = {"catalog": "main", "schema": "silver", "table": "customers"}
    (tmp_path / "customers.ingestion.json").write_text(
        json.dumps({"source": {"type": "table", "table": "main.raw.customers"}, "target": target, "mode": "scd0_append"}),
        encoding="utf-8",
    )
    (tmp_path / "customers.annotations.json").write_text(
        json.dumps({"target": target, "table": {"description": "Customers"}}),
        encoding="utf-8",
    )
    (tmp_path / "customers.access.json").write_text(
        json.dumps({"target": target, "grants": [{"principal": "analysts", "privileges": ["SELECT"]}]}),
        encoding="utf-8",
    )
    runner = FakeRunner()

    governance = apply_databricks_governance_bundle(base, runner=runner)
    annotations = apply_databricks_annotations_bundle(base, runner=FakeRunner())
    access = apply_databricks_access_bundle(base, runner=FakeRunner())

    assert governance["status"] == "SUCCESS"
    assert annotations["status"] == "SUCCESS"
    assert access["status"] == "SUCCESS"
    assert any(statement.startswith("COMMENT ON TABLE") for statement in runner.statements)
    assert any(statement.startswith("GRANT SELECT") for statement in runner.statements)


def _install_fake_pyspark(monkeypatch) -> None:
    pyspark = types.ModuleType("pyspark")
    sql = types.ModuleType("pyspark.sql")
    functions = types.SimpleNamespace(expr=lambda value: value)
    sql.functions = functions
    monkeypatch.setitem(sys.modules, "pyspark", pyspark)
    monkeypatch.setitem(sys.modules, "pyspark.sql", sql)
