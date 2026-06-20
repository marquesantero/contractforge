"""Databricks SQL MERGE execution helpers."""

from __future__ import annotations

from typing import Any, Protocol

from contractforge_core.semantic import SemanticContract
from contractforge_core.execution import ExecutionOutcome
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_identifier, quote_table_name


class SqlRunner(Protocol):
    def sql(self, statement: str) -> Any:
        ...


def render_scd1_merge_sql(
    *,
    target_table: str,
    source_view: str,
    merge_keys: tuple[str, ...],
    source_columns: tuple[str, ...],
    target_partition_predicate: str | None = None,
) -> str:
    """Render deterministic SCD1 current-state MERGE SQL."""
    if not merge_keys:
        raise ValueError("scd1_upsert requires merge_keys")
    if not source_columns:
        raise ValueError("scd1_upsert requires source_columns")

    missing_keys = [key for key in merge_keys if key not in source_columns]
    if missing_keys:
        raise ValueError(f"merge_keys missing from source_columns: {missing_keys}")

    update_columns = tuple(column for column in source_columns if column not in merge_keys)
    key_condition = " AND ".join(
        f"t.{quote_identifier(key)} <=> s.{quote_identifier(key)}" for key in merge_keys
    )
    if target_partition_predicate:
        key_condition = f"{key_condition} AND {target_partition_predicate}"
    update_set = ", ".join(
        f"t.{quote_identifier(column)} = s.{quote_identifier(column)}" for column in update_columns
    )
    insert_columns = ", ".join(quote_identifier(column) for column in source_columns)
    insert_values = ", ".join(f"s.{quote_identifier(column)}" for column in source_columns)

    lines = [
        f"MERGE INTO {quote_table_name(target_table)} t",
        f"USING {quote_table_name(source_view)} s",
        f"ON {key_condition}",
    ]
    if update_set:
        lines.append(f"WHEN MATCHED THEN UPDATE SET {update_set}")
    lines.append(f"WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})")
    return "\n".join(lines)


def execute_scd1_merge(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    source_view: str,
    source_columns: tuple[str, ...],
    target_partition_predicate: str | None = None,
) -> ExecutionOutcome:
    if contract.write.mode != "scd1_upsert":
        raise ValueError(f"execute_scd1_merge only supports scd1_upsert, got {contract.write.mode}")

    target = target_full_name(contract)
    statement = render_scd1_merge_sql(
        target_table=target,
        source_view=source_view,
        merge_keys=contract.write.merge_keys,
        source_columns=source_columns,
        target_partition_predicate=target_partition_predicate,
    )
    runner.sql(statement)
    return ExecutionOutcome(
        status="SUCCESS",
        operation="scd1_sql_merge",
        target=target,
        metrics={"source_columns": len(source_columns), "merge_keys": len(contract.write.merge_keys)},
        sql=statement,
    )
