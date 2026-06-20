"""Databricks Delta DDL for operational state tables."""

from __future__ import annotations

from contractforge_core.evidence import STATE_TABLE_SCHEMAS
from contractforge_databricks.sql import quote_table_name
from contractforge_databricks.state.tables import state_table_names


def render_create_state_tables_sql(*, catalog: str = "main", schema: str = "ops") -> str:
    names = state_table_names(catalog, schema)
    statements = [f"CREATE SCHEMA IF NOT EXISTS {quote_table_name(f'{catalog}.{schema}')};"]
    for name, table in names.items():
        statements.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {quote_table_name(table)} (",
                    f"  {STATE_TABLE_SCHEMAS[name]}",
                    ")",
                    "USING DELTA;",
                ]
            )
        )
    return "\n\n".join(statements) + "\n"
