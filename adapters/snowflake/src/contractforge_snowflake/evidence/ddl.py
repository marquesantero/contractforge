"""Render Snowflake DDL for canonical ContractForge evidence tables."""

from __future__ import annotations

from contractforge_core.evidence.control_tables import (
    EVIDENCE_TABLES,
    EVIDENCE_TABLE_SCHEMAS,
    STATE_TABLES,
    STATE_TABLE_SCHEMAS,
)
from contractforge_snowflake.naming import quote_identifier


def render_create_evidence_tables_sql(
    *,
    database: str = "CONTRACTFORGE",
    schema: str = "CF_EVIDENCE",
    create_database: bool = True,
    create_schema: bool = True,
) -> str:
    return _render_table_group_sql(
        EVIDENCE_TABLES,
        EVIDENCE_TABLE_SCHEMAS,
        database=database,
        schema=schema,
        create_database=create_database,
        create_schema=create_schema,
    )


def render_create_state_tables_sql(
    *,
    database: str = "CONTRACTFORGE",
    schema: str = "CF_EVIDENCE",
    create_database: bool = True,
    create_schema: bool = True,
) -> str:
    return _render_table_group_sql(
        STATE_TABLES,
        STATE_TABLE_SCHEMAS,
        database=database,
        schema=schema,
        create_database=create_database,
        create_schema=create_schema,
    )


def _render_table_group_sql(
    table_names: dict[str, str],
    table_schemas: dict[str, str],
    *,
    database: str,
    schema: str,
    create_database: bool,
    create_schema: bool,
) -> str:
    statements = []
    if create_database:
        statements.append(f"CREATE DATABASE IF NOT EXISTS {quote_identifier(database)};")
    if create_schema:
        statements.append(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(database)}.{quote_identifier(schema)};")
    for key, table_name in table_names.items():
        statements.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {quote_identifier(database)}.{quote_identifier(schema)}.{quote_identifier(table_name)} (",
                    f"  {_format_columns(table_schemas[key])}",
                    ");",
                ]
            )
        )
    return "\n\n".join(statements) + "\n"


def _format_columns(schema: str) -> str:
    return ",\n  ".join(_format_column(column) for column in schema.split(","))


def _format_column(column: str) -> str:
    text = column.strip()
    name, _, remainder = text.partition(" ")
    if not name or not remainder:
        raise ValueError(f"Invalid Snowflake evidence column definition: {column!r}")
    return f"{quote_identifier(name)} {remainder.strip()}"
