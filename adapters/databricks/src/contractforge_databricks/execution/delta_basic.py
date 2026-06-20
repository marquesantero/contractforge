"""Databricks Delta append and overwrite helpers."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_core.execution import ExecutionOutcome
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_table_name


def render_append_sql(*, target_table: str, source_view: str) -> str:
    return f"INSERT INTO {quote_table_name(target_table)}\nSELECT * FROM {quote_table_name(source_view)}"


def render_overwrite_sql(*, target_table: str, source_view: str) -> str:
    return f"INSERT OVERWRITE TABLE {quote_table_name(target_table)}\nSELECT * FROM {quote_table_name(source_view)}"


def execute_append(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    source_view: str,
) -> ExecutionOutcome:
    if contract.write.mode != "scd0_append":
        raise ValueError(f"execute_append only supports scd0_append, got {contract.write.mode}")
    target = target_full_name(contract)
    statement = render_append_sql(target_table=target, source_view=source_view)
    runner.sql(statement)
    return ExecutionOutcome(
        status="SUCCESS",
        operation="delta_append",
        target=target,
        metrics={},
        sql=statement,
    )


def execute_overwrite(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    source_view: str,
) -> ExecutionOutcome:
    if contract.write.mode != "scd0_overwrite":
        raise ValueError(f"execute_overwrite only supports scd0_overwrite, got {contract.write.mode}")
    target = target_full_name(contract)
    statement = render_overwrite_sql(target_table=target, source_view=source_view)
    runner.sql(statement)
    return ExecutionOutcome(
        status="SUCCESS",
        operation="delta_overwrite",
        target=target,
        metrics={},
        sql=statement,
    )
