"""Runtime bootstrap for Databricks control tables."""

from __future__ import annotations

from contractforge_databricks.evidence import render_create_evidence_tables_sql
from contractforge_databricks.execution import SqlRunner
from contractforge_databricks.state import render_create_state_tables_sql


def ensure_control_tables(*, runner: SqlRunner, catalog: str = "main", schema: str = "ops") -> None:
    """Create Databricks evidence and state tables when they do not exist."""
    for statement in _split_sql(render_create_evidence_tables_sql(catalog=catalog, schema=schema)):
        runner.sql(statement)
    for statement in _split_sql(render_create_state_tables_sql(catalog=catalog, schema=schema)):
        runner.sql(statement)


def _split_sql(script: str) -> tuple[str, ...]:
    return tuple(statement.strip() for statement in script.split(";") if statement.strip())
