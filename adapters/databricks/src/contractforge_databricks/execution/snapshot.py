"""ContractForge-compatible snapshot soft delete Delta MERGE SQL."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_core.execution import ExecutionOutcome
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_identifier, quote_table_name


def render_snapshot_soft_delete_sql(
    *,
    target_table: str,
    source_view: str,
    merge_keys: tuple[str, ...],
    source_columns: tuple[str, ...],
) -> str:
    if not merge_keys:
        raise ValueError("snapshot_soft_delete requires merge_keys")
    _require_columns(source_columns, merge_keys, "merge_keys")
    _require_columns(source_columns, ("is_active", "deleted_at", "row_hash"))

    key_condition = " AND ".join(
        f"t.{quote_identifier(key)} <=> s.{quote_identifier(key)}" for key in merge_keys
    )
    update_columns = tuple(column for column in source_columns if column not in merge_keys)
    update_set = ", ".join(
        f"t.{quote_identifier(column)} = s.{quote_identifier(column)}" for column in update_columns
    )
    insert_columns = ", ".join(quote_identifier(column) for column in source_columns)
    insert_values = ", ".join(f"s.{quote_identifier(column)}" for column in source_columns)

    return "\n".join(
        [
            f"MERGE INTO {quote_table_name(target_table)} t",
            f"USING {quote_table_name(source_view)} s",
            f"ON {key_condition}",
            f"WHEN MATCHED AND (NOT (t.`row_hash` <=> s.`row_hash`) OR t.`is_active` = false) THEN UPDATE SET {update_set}",
            f"WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})",
            "WHEN NOT MATCHED BY SOURCE AND t.`is_active` = true THEN UPDATE SET",
            "  t.`is_active` = false,",
            "  t.`deleted_at` = current_timestamp()",
        ]
    )


def execute_snapshot_soft_delete(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    source_view: str,
    source_columns: tuple[str, ...],
) -> ExecutionOutcome:
    if contract.write.mode != "snapshot_soft_delete":
        raise ValueError(f"execute_snapshot_soft_delete only supports snapshot_soft_delete, got {contract.write.mode}")
    target = target_full_name(contract)
    statement = render_snapshot_soft_delete_sql(
        target_table=target,
        source_view=source_view,
        merge_keys=contract.write.merge_keys,
        source_columns=source_columns,
    )
    runner.sql(statement)
    return ExecutionOutcome(
        status="SUCCESS",
        operation="core_managed_snapshot_soft_delete_delta_merge",
        target=target,
        metrics={"source_columns": len(source_columns), "merge_keys": len(contract.write.merge_keys)},
        sql=statement,
    )


def _require_columns(columns: tuple[str, ...], required: tuple[str, ...], context: str = "required columns") -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"prepared snapshot source is missing {context}: {missing}")
