"""Dispatch prepared Databricks views to write-mode executors."""

from __future__ import annotations

from contractforge_core.runtime import PreparedInput, QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.execution import (
    ExecutionOutcome,
    SqlRunner,
    execute_append,
    execute_hash_diff_insert,
    execute_overwrite,
    execute_replace_partitions,
    execute_scd1_merge,
    execute_scd2_merge,
    execute_snapshot_soft_delete,
)
from contractforge_databricks.write_modes.registry import execute_registered_write_mode


def execute_prepared_write(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    prepared: PreparedInput,
    target_partition_predicate: str | None = None,
    replace_partition_predicate: str | None = None,
    target_schema: dict[str, str] | None = None,
    query_one: QueryOne | None = None,
) -> ExecutionOutcome:
    kwargs = {"runner": runner, "contract": contract, "source_view": prepared.source_view}
    if contract.write.mode == "scd0_append":
        return execute_append(**kwargs)
    if contract.write.mode == "scd0_overwrite":
        return execute_overwrite(**kwargs)
    if contract.write.mode == "scd1_upsert":
        if replace_partition_predicate:
            return execute_replace_partitions(**kwargs, predicate=replace_partition_predicate)
        return execute_scd1_merge(
            **kwargs,
            source_columns=prepared.source_columns,
            target_partition_predicate=target_partition_predicate,
        )
    if contract.write.mode == "scd1_hash_diff":
        return execute_hash_diff_insert(
            **kwargs,
            source_columns=prepared.source_columns,
            target_schema=target_schema,
            query_one=query_one,
        )
    if contract.write.mode == "scd2_historical":
        return execute_scd2_merge(**kwargs, insert_columns=prepared.source_columns)
    if contract.write.mode == "snapshot_soft_delete":
        return execute_snapshot_soft_delete(**kwargs, source_columns=prepared.source_columns)
    if contract.write.mode.startswith("custom:"):
        return execute_registered_write_mode(
            contract.write.mode,
            runner=runner,
            contract=contract,
            prepared=prepared,
            target_partition_predicate=target_partition_predicate,
            replace_partition_predicate=replace_partition_predicate,
            target_schema=target_schema,
            query_one=query_one,
        )
    raise ValueError(f"Unsupported Databricks write mode: {contract.write.mode}")
