from __future__ import annotations

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.contract_extensions import normalize_databricks_contract
from contractforge_databricks.execution import (
    execute_table_setup,
    render_create_delta_table_sql,
    render_create_schema_sql,
    render_delta_properties_sql,
    render_table_setup_sql,
)


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def _contract(payload: dict):
    return semantic_contract_from_mapping(normalize_databricks_contract(payload))


def test_render_create_delta_table_sql_with_partition() -> None:
    sql = render_create_delta_table_sql(
        target_table="main.bronze.orders",
        columns={"id": "BIGINT", "dt": "DATE"},
        partition_column="dt",
    )

    assert sql == "CREATE TABLE IF NOT EXISTS `main`.`bronze`.`orders` (`id` BIGINT, `dt` DATE) USING DELTA PARTITIONED BY (`dt`)"


def test_render_create_delta_table_sql_with_multiple_partitions() -> None:
    sql = render_create_delta_table_sql(
        target_table="main.bronze.orders",
        columns={"id": "BIGINT", "dt": "DATE", "region": "STRING"},
        partition_columns=("dt", "region"),
    )

    assert sql == (
        "CREATE TABLE IF NOT EXISTS `main`.`bronze`.`orders` "
        "(`id` BIGINT, `dt` DATE, `region` STRING) USING DELTA PARTITIONED BY (`dt`, `region`)"
    )


def test_render_create_delta_table_sql_rejects_missing_partition_column() -> None:
    with pytest.raises(ValueError, match="partition_columns missing"):
        render_create_delta_table_sql(target_table="main.bronze.orders", columns={"id": "BIGINT"}, partition_column="dt")


def test_render_create_schema_sql_quotes_namespace() -> None:
    assert render_create_schema_sql(namespace="main.bronze") == "CREATE SCHEMA IF NOT EXISTS `main`.`bronze`"
    assert render_create_schema_sql(namespace=None) is None


def test_render_delta_properties_sql_quotes_properties() -> None:
    sql = render_delta_properties_sql(
        target_table="main.bronze.orders",
        properties={"delta.autoOptimize.optimizeWrite": "true", "owner": "O'Reilly"},
    )

    assert sql is not None
    assert "ALTER TABLE `main`.`bronze`.`orders` SET TBLPROPERTIES" in sql
    assert "'owner' = 'O''Reilly'" in sql


def test_render_table_setup_sql_uses_databricks_extensions() -> None:
    contract = _contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "extensions": {
                "databricks": {
                    "partition_column": "dt",
                    "cluster_columns": ["id"],
                    "delta_properties": {"delta.enableChangeDataFeed": "true"},
                }
            },
        }
    )

    statements = render_table_setup_sql(contract, columns={"id": "BIGINT", "dt": "DATE"})

    assert statements[0] == "CREATE SCHEMA IF NOT EXISTS `main`.`bronze`"
    assert statements[1] == "CREATE TABLE IF NOT EXISTS `main`.`bronze`.`orders` (`id` BIGINT, `dt` DATE) USING DELTA"
    assert statements[2] == "ALTER TABLE `main`.`bronze`.`orders` CLUSTER BY (`id`)"
    assert statements[3] == "ALTER TABLE `main`.`bronze`.`orders` SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')"


def test_render_table_setup_sql_rejects_missing_cluster_column() -> None:
    contract = _contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "extensions": {"databricks": {"cluster_columns": ["missing_id"]}},
        }
    )

    with pytest.raises(ValueError, match="cluster_columns missing"):
        render_table_setup_sql(contract, columns={"id": "BIGINT"})


def test_render_table_setup_sql_uses_canonical_partition_columns_extension() -> None:
    contract = _contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "extensions": {"databricks": {"partition_columns": ["dt", "region"]}},
        }
    )

    statements = render_table_setup_sql(contract, columns={"id": "BIGINT", "dt": "DATE", "region": "STRING"})

    assert statements[1].endswith("USING DELTA PARTITIONED BY (`dt`, `region`)")


def test_execute_table_setup_runs_all_statements() -> None:
    runner = FakeRunner()
    contract = _contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "extensions": {"databricks": {"delta_properties": {"delta.enableChangeDataFeed": "true"}}},
        }
    )

    statements = execute_table_setup(runner=runner, contract=contract, columns={"id": "BIGINT"})

    assert runner.statements == list(statements)
