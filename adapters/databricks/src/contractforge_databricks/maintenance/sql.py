"""Databricks table maintenance SQL helpers."""

from __future__ import annotations

from dataclasses import dataclass

from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.sql import quote_identifier, quote_table_name


@dataclass(frozen=True)
class MaintenancePlan:
    target_table: str
    optimize: bool = False
    zorder_columns: tuple[str, ...] = ()
    vacuum_retention_hours: int | None = None
    analyze: bool = False
    delta_properties: dict[str, str] | None = None


def render_optimize_sql(target_table: str, *, zorder_columns: tuple[str, ...] = ()) -> str:
    statement = f"OPTIMIZE {quote_table_name(target_table)}"
    if zorder_columns:
        columns = ", ".join(quote_identifier(column) for column in zorder_columns)
        statement += f" ZORDER BY ({columns})"
    return statement


def render_vacuum_sql(target_table: str, *, retention_hours: int) -> str:
    if retention_hours < 0:
        raise ValueError("vacuum retention must be non-negative")
    return f"VACUUM {quote_table_name(target_table)} RETAIN {retention_hours} HOURS"


def render_analyze_sql(target_table: str) -> str:
    return f"ANALYZE TABLE {quote_table_name(target_table)} COMPUTE STATISTICS"


def render_alter_table_properties_sql(target_table: str, properties: dict[str, str]) -> str:
    if not properties:
        raise ValueError("delta properties must not be empty")
    props = ", ".join(f"{_sql_string(key)} = {_sql_string(value)}" for key, value in sorted(properties.items()))
    return f"ALTER TABLE {quote_table_name(target_table)} SET TBLPROPERTIES ({props})"


def render_maintenance_plan_sql(plan: MaintenancePlan) -> tuple[str, ...]:
    statements: list[str] = []
    if plan.delta_properties:
        statements.append(render_alter_table_properties_sql(plan.target_table, plan.delta_properties))
    if plan.optimize:
        statements.append(render_optimize_sql(plan.target_table, zorder_columns=plan.zorder_columns))
    if plan.vacuum_retention_hours is not None:
        statements.append(render_vacuum_sql(plan.target_table, retention_hours=plan.vacuum_retention_hours))
    if plan.analyze:
        statements.append(render_analyze_sql(plan.target_table))
    return tuple(statements)


def execute_maintenance_plan(runner: SqlRunner, plan: MaintenancePlan) -> tuple[str, ...]:
    statements = render_maintenance_plan_sql(plan)
    for statement in statements:
        runner.sql(statement)
    return statements


def _sql_string(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"

