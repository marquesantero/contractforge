"""Databricks Delta table setup SQL helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_identifier, quote_table_name, sql_literal


def render_create_delta_table_sql(
    *,
    target_table: str,
    columns: dict[str, str],
    partition_column: str | None = None,
    partition_columns: tuple[str, ...] = (),
) -> str:
    if not columns:
        raise ValueError("Delta table creation requires at least one column")
    partitions = tuple(partition_columns or ((partition_column,) if partition_column else ()))
    missing_partition_columns = [column for column in partitions if column not in columns]
    if missing_partition_columns:
        raise ValueError(f"partition_columns missing from source columns: {missing_partition_columns}")
    cols_sql = ", ".join(f"{quote_identifier(name)} {data_type}" for name, data_type in columns.items())
    partition_sql = f" PARTITIONED BY ({', '.join(quote_identifier(column) for column in partitions)})" if partitions else ""
    return f"CREATE TABLE IF NOT EXISTS {quote_table_name(target_table)} ({cols_sql}) USING DELTA{partition_sql}"


def render_create_schema_sql(*, namespace: str | None) -> str | None:
    if not namespace:
        return None
    return f"CREATE SCHEMA IF NOT EXISTS {quote_table_name(namespace)}"


def render_cluster_by_sql(*, target_table: str, cluster_columns: tuple[str, ...]) -> str | None:
    if not cluster_columns:
        return None
    columns_sql = ", ".join(quote_identifier(column) for column in cluster_columns)
    return f"ALTER TABLE {quote_table_name(target_table)} CLUSTER BY ({columns_sql})"


def render_delta_properties_sql(*, target_table: str, properties: dict[str, Any] | None) -> str | None:
    if not properties:
        return None
    props_sql = ", ".join(f"{sql_literal(key)} = {sql_literal(value)}" for key, value in sorted(properties.items()))
    return f"ALTER TABLE {quote_table_name(target_table)} SET TBLPROPERTIES ({props_sql})"


def render_table_setup_sql(
    contract: SemanticContract,
    *,
    columns: dict[str, str],
) -> tuple[str, ...]:
    extensions = databricks_extensions(contract)
    target = target_full_name(contract)
    cluster_columns = tuple(str(column) for column in extensions.get("cluster_columns") or ())
    partition_columns = _partition_columns(extensions)
    missing_cluster_columns = [column for column in cluster_columns if column not in columns]
    if missing_cluster_columns:
        raise ValueError(f"cluster_columns missing from source columns: {missing_cluster_columns}")
    if cluster_columns and partition_columns:
        partition_columns = ()
    statements = [
        render_create_schema_sql(namespace=contract.target.namespace),
        render_create_delta_table_sql(
            target_table=target,
            columns=columns,
            partition_columns=partition_columns,
        )
    ]
    cluster_sql = render_cluster_by_sql(target_table=target, cluster_columns=cluster_columns)
    properties_sql = render_delta_properties_sql(target_table=target, properties=extensions.get("delta_properties"))
    return tuple(statement for statement in (*statements, cluster_sql, properties_sql) if statement)


def execute_table_setup(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    columns: dict[str, str],
) -> tuple[str, ...]:
    statements = render_table_setup_sql(contract, columns=columns)
    for statement in statements:
        runner.sql(statement)
    return statements


def _partition_columns(extensions: dict[str, Any]) -> tuple[str, ...]:
    value = extensions.get("partition_columns")
    if value:
        if isinstance(value, str):
            return (value,)
        return tuple(str(column) for column in value)
    single = str(extensions.get("partition_column") or "")
    return (single,) if single else ()
