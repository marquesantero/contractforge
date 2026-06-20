"""ContractForge-compatible SCD1 hash-diff append SQL."""

from __future__ import annotations

from contractforge_core.runtime import QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_core.execution import ExecutionOutcome
from contractforge_databricks.execution.hash_diff_latest import (
    resolve_hash_diff_latest_selection,
    validate_hash_diff_target_latest,
)
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_identifier, quote_table_name


def render_hash_diff_insert_sql(
    *,
    target_table: str,
    source_view: str,
    merge_keys: tuple[str, ...],
    source_columns: tuple[str, ...],
    row_hash_column: str = "row_hash",
    latest_order_by: str | None = None,
) -> str:
    if not merge_keys:
        raise ValueError("scd1_hash_diff requires merge_keys")
    _require_columns(source_columns, merge_keys, "merge_keys")
    if row_hash_column not in source_columns:
        raise ValueError(f"prepared hash-diff source is missing {row_hash_column}")

    join_condition = " AND ".join(
        f"t.{quote_identifier(key)} <=> s.{quote_identifier(key)}" for key in merge_keys
    )
    null_condition = " AND ".join(f"t.{quote_identifier(key)} IS NULL" for key in merge_keys)
    columns = ", ".join(quote_identifier(column) for column in source_columns)
    values = ", ".join(f"s.{quote_identifier(column)}" for column in source_columns)

    target_relation = _target_latest_relation(
        target_table=target_table,
        merge_keys=merge_keys,
        row_hash_column=row_hash_column,
        latest_order_by=latest_order_by,
    )
    lines = [
        f"INSERT INTO {quote_table_name(target_table)} ({columns})",
        f"SELECT {values}",
        f"FROM {quote_table_name(source_view)} s",
        "LEFT JOIN (",
        *target_relation,
        ") t",
        f"ON {join_condition}",
        f"WHERE ({null_condition}) OR NOT (t.{quote_identifier(row_hash_column)} <=> s.{quote_identifier(row_hash_column)})",
    ]
    return "\n".join(lines)


def _target_latest_relation(
    *,
    target_table: str,
    merge_keys: tuple[str, ...],
    row_hash_column: str,
    latest_order_by: str | None,
) -> list[str]:
    selected = f"{', '.join(quote_identifier(key) for key in merge_keys)}, {quote_identifier(row_hash_column)}"
    if not latest_order_by:
        return [f"  SELECT {selected}", f"  FROM {quote_table_name(target_table)}"]
    partition = ", ".join(quote_identifier(key) for key in merge_keys)
    return [
        f"  SELECT {selected}",
        "  FROM (",
        f"    SELECT {selected},",
        f"      row_number() OVER (PARTITION BY {partition} ORDER BY {latest_order_by}) AS __cf_latest_rank",
        f"    FROM {quote_table_name(target_table)}",
        "  ) latest",
        "  WHERE __cf_latest_rank = 1",
    ]


def _require_columns(columns: tuple[str, ...], required: tuple[str, ...], context: str) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"prepared hash-diff source is missing {context}: {missing}")


def execute_hash_diff_insert(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    source_view: str,
    source_columns: tuple[str, ...],
    target_schema: dict[str, str] | None = None,
    query_one: QueryOne | None = None,
) -> ExecutionOutcome:
    if contract.write.mode != "scd1_hash_diff":
        raise ValueError(f"execute_hash_diff_insert only supports scd1_hash_diff, got {contract.write.mode}")
    target = target_full_name(contract)
    merge_keys = contract.write.merge_keys or contract.write.hash_keys
    selection = resolve_hash_diff_latest_selection(contract, target_schema)
    validate_hash_diff_target_latest(
        query_one=query_one,
        target_table=target,
        merge_keys=merge_keys,
        selection=selection,
    )
    statement = render_hash_diff_insert_sql(
        target_table=target,
        source_view=source_view,
        merge_keys=merge_keys,
        source_columns=source_columns,
        latest_order_by=selection.order_by,
    )
    runner.sql(statement)
    return ExecutionOutcome(
        status="SUCCESS",
        operation="core_managed_hash_diff_delta",
        target=target,
        metrics={
            "source_columns": len(source_columns),
            "merge_keys": len(merge_keys),
            "hash_keys": len(contract.write.hash_keys),
            "target_latest_ordered": bool(selection.order_by),
            "target_latest_reason": selection.reason,
        },
        sql=statement,
    )
