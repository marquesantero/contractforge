"""Fabric Lakehouse Delta DDL for operational state tables."""

from __future__ import annotations

from contractforge_core.evidence import STATE_TABLE_SCHEMAS
from contractforge_fabric.state.tables import state_table_names
from contractforge_fabric.sql import delta_schema, quote_table_name, schema_statements


def render_create_state_tables_sql(*, schema: str = "contractforge", create_schema: bool = True) -> str:
    statements = schema_statements(schema, create_schema=create_schema)
    for name, table in state_table_names(schema).items():
        statements.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {quote_table_name(table)} (",
                    f"  {delta_schema(STATE_TABLE_SCHEMAS[name])}",
                    ")",
                    "USING DELTA;",
                ]
            )
        )
    return "\n\n".join(statements) + "\n"


__all__ = ["render_create_state_tables_sql"]
