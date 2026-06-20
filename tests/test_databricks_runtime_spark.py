from __future__ import annotations

import ast
from pathlib import Path
import logging

from contractforge_databricks.runtime.spark import (
    _SERVERLESS_CACHE,
    detect_serverless,
    runtime_info,
    safe_cache,
    safe_unpersist,
    schema_signature,
    sync_delta_schema,
    table_exists,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "adapters" / "databricks" / "src" / "contractforge_databricks" / "runtime" / "spark.py"


class FakeDataType:
    def __init__(self, type_name: str) -> None:
        self.type_name = type_name

    def simpleString(self) -> str:
        return self.type_name

    def typeName(self) -> str:
        return self.type_name


class FakeField:
    def __init__(self, name: str, type_name: str, nullable: bool = True) -> None:
        self.name = name
        self.dataType = FakeDataType(type_name)
        self.nullable = nullable


class FakeSchema:
    def __init__(self, fields: list[FakeField]) -> None:
        self.fields = fields


class FakeDataFrame:
    def __init__(self) -> None:
        self.schema = FakeSchema([FakeField("id", "bigint", False), FakeField("name", "string")])
        self.cached = False
        self.unpersisted = False

    def cache(self):
        self.cached = True
        return self

    def unpersist(self) -> None:
        self.unpersisted = True


class FakeCatalog:
    def __init__(self, exists: bool, *, fail: bool = False) -> None:
        self.exists = exists
        self.fail = fail

    def tableExists(self, name: str) -> bool:
        if self.fail:
            raise RuntimeError("catalog unavailable")
        return self.exists


class FakeSpark:
    version = "16.4"

    def __init__(self, exists: bool = True, conf: dict[str, str] | None = None, catalog_fails: bool = False) -> None:
        self.catalog = FakeCatalog(exists, fail=catalog_fails)
        self.statements: list[str] = []
        self.sparkContext = FakeSparkContext(conf or {})

    def sql(self, statement: str) -> None:
        self.statements.append(statement)
        if statement.startswith("DESCRIBE") and not self.catalog.exists:
            raise RuntimeError("not found")


class FakeSparkContext:
    def __init__(self, conf: dict[str, str]) -> None:
        self._conf = FakeConf(conf)

    def getConf(self):
        return self._conf


class FakeConf:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.get_calls = 0
        self.get_all_calls = 0

    def get(self, key: str, default=None):
        self.get_calls += 1
        return self.values.get(key, default)

    def getAll(self):
        self.get_all_calls += 1
        return list(self.values.items())


def test_runtime_spark_module_keeps_pyspark_import_lazy() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    top_level_imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.append(node.module)

    assert "pyspark.sql" not in top_level_imports


def test_safe_cache_and_unpersist_can_skip_serverless() -> None:
    df = FakeDataFrame()

    assert safe_cache(df, serverless=True) is df
    safe_unpersist(df, serverless=True)

    assert df.cached is False
    assert df.unpersisted is False


def test_safe_cache_and_unpersist_use_dataframe_when_allowed() -> None:
    df = FakeDataFrame()

    assert safe_cache(df, serverless=False) is df
    safe_unpersist(df, serverless=False)

    assert df.cached is True
    assert df.unpersisted is True


def test_table_exists_uses_catalog_and_describe_fallback() -> None:
    assert table_exists("main.silver.orders", spark=FakeSpark(exists=True)) is True
    assert table_exists("main.silver.orders", spark=FakeSpark(exists=False)) is False


def test_table_exists_logs_catalog_fallback(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="contractforge_databricks.runtime.spark")

    assert table_exists("main.silver.orders", spark=FakeSpark(exists=True, catalog_fails=True)) is True

    assert "falling back to DESCRIBE TABLE" in caplog.text


def test_schema_signature_matches_expected_shape() -> None:
    assert schema_signature(FakeDataFrame()) == '[["id", "bigint", false], ["name", "string", true]]'


def test_sync_delta_schema_applies_additive_and_widening_changes() -> None:
    spark = FakeSpark(exists=True)
    change = {"column": "id", "source": "bigint", "allowed": True}

    sync_delta_schema(
        df=FakeDataFrame(),
        target_table="main.silver.orders",
        schema_changes={"added_columns": ["name"], "type_changes": [change]},
        policy="permissive",
        spark=spark,
    )

    assert "ALTER TABLE `main`.`silver`.`orders` ADD COLUMNS (`name` string)" in spark.statements
    assert "ALTER TABLE `main`.`silver`.`orders` ALTER COLUMN `id` TYPE bigint" in spark.statements
    assert change["applied"] is True


def test_runtime_info_reports_classic_without_active_spark() -> None:
    info = runtime_info(spark=FakeSpark())

    assert info["runtime_type"] == "classic"
    assert info["spark_version"] == "16.4"


def test_runtime_info_uses_shared_serverless_classification() -> None:
    info = runtime_info(
        spark=FakeSpark(
            conf={
                "spark.databricks.job.id": "42",
                "spark.databricks.job.runId": "99",
            }
        )
    )

    assert info["runtime_type"] == "serverless"


def test_detect_serverless_caches_by_session() -> None:
    _SERVERLESS_CACHE.clear()
    spark = FakeSpark(
        conf={
            "spark.databricks.job.id": "42",
            "spark.databricks.job.runId": "99",
        }
    )

    assert detect_serverless(spark) is True
    first_get_calls = spark.sparkContext.getConf().get_calls
    first_get_all_calls = spark.sparkContext.getConf().get_all_calls
    assert detect_serverless(spark) is True

    assert spark.sparkContext.getConf().get_calls == first_get_calls
    assert spark.sparkContext.getConf().get_all_calls == first_get_all_calls
