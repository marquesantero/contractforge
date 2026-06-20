"""Databricks selective partition replacement helpers."""

from __future__ import annotations

from contractforge_core.execution import ExecutionOutcome
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_table_name


def render_replace_partitions_sql(*, target_table: str, source_view: str, predicate: str) -> str:
    if not predicate:
        raise ValueError("replace_partitions requires a non-empty partition predicate")
    return (
        f"INSERT INTO TABLE {quote_table_name(target_table)} BY NAME\n"
        f"REPLACE WHERE {predicate}\n"
        f"SELECT * FROM {quote_table_name(source_view)}"
    )


def execute_replace_partitions(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    source_view: str,
    predicate: str | None,
) -> ExecutionOutcome:
    if contract.write.mode != "scd1_upsert":
        raise ValueError(f"execute_replace_partitions only supports scd1_upsert, got {contract.write.mode}")
    target = target_full_name(contract)
    statement = render_replace_partitions_sql(target_table=target, source_view=source_view, predicate=predicate or "")
    runner.sql(statement)
    return ExecutionOutcome(
        status="SUCCESS",
        operation="delta_replace_partitions",
        target=target,
        metrics={"replace_predicate": predicate},
        sql=statement,
    )
