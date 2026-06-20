"""Runtime partition-scope helpers for Databricks writes."""

from __future__ import annotations

from typing import Any

from contractforge_core.runtime import PreparedInput, QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.partitioning import render_partition_in_predicate
from contractforge_databricks.sql import quote_identifier, quote_table_name


def target_partition_predicate(
    *,
    contract: SemanticContract,
    prepared: PreparedInput,
    query_one: QueryOne | None,
) -> str | None:
    extensions = databricks_extensions(contract)
    if contract.write.mode != "scd1_upsert" or extensions.get("merge_strategy") != "delta_by_partition":
        return None
    column = str(extensions.get("merge_partition_column") or extensions.get("partition_column") or "")
    if not column:
        raise ValueError("merge_strategy=delta_by_partition requires merge_partition_column or partition_column")
    if column not in prepared.source_columns:
        raise ValueError(f"partition column {column!r} is not present in prepared source columns")
    values = _partition_values(prepared, column, query_one)
    return f"t.{render_partition_in_predicate(column, values)}"


def replace_partition_predicate(
    *,
    contract: SemanticContract,
    prepared: PreparedInput,
    query_one: QueryOne | None,
) -> str | None:
    extensions = databricks_extensions(contract)
    if contract.write.mode != "scd1_upsert" or extensions.get("merge_strategy") != "replace_partitions":
        return None
    _validate_replace_partitions_contract(contract, extensions)
    column = str(extensions.get("merge_partition_column") or "")
    if column not in prepared.source_columns:
        raise ValueError(f"merge_partition_column {column!r} is not present in prepared source columns")
    values = _partition_values(prepared, column, query_one)
    return render_partition_in_predicate(column, values)


def _validate_replace_partitions_contract(contract: SemanticContract, extensions: dict[str, Any]) -> None:
    column = str(extensions.get("merge_partition_column") or "")
    if not column:
        raise ValueError("merge_strategy=replace_partitions requires merge_partition_column")
    partition_column = extensions.get("partition_column")
    if partition_column and partition_column != column:
        raise ValueError("merge_strategy=replace_partitions requires partition_column equal to merge_partition_column")
    if extensions.get("replace_partitions_source_complete") or _source_declares_complete(contract):
        return
    raise ValueError(
        "merge_strategy=replace_partitions requires replace_partitions_source_complete=true "
        "or source.read.source_complete=true/source.read.full_snapshot=true"
    )


def _source_declares_complete(contract: SemanticContract) -> bool:
    source = contract.source.raw or {}
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    return bool(read.get("source_complete") or read.get("full_snapshot") or source.get("source_complete"))


def _partition_values(prepared: PreparedInput, column: str, query_one: QueryOne | None) -> tuple[Any, ...]:
    if query_one is None:
        metadata_values = (prepared.source_metadata or {}).get("affected_partition_values")
        if metadata_values:
            return tuple(metadata_values)
        raise ValueError("delta_by_partition requires query_one or prepared.source_metadata.affected_partition_values")
    row = query_one(
        f"SELECT collect_set({quote_identifier(column)}) AS partition_values "
        f"FROM {quote_table_name(prepared.source_view)}"
    )
    values = _row_value(row, "partition_values")
    if not values:
        raise ValueError("delta_by_partition could not detect affected partition values")
    return tuple(values)


def _row_value(row: Any, key: str) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    if hasattr(row, "asDict"):
        return row.asDict().get(key)
    return getattr(row, key, None)
