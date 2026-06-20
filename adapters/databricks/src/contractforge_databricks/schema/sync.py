"""Render Databricks SQL for validated schema changes."""

from __future__ import annotations

from contractforge_core.schema import SchemaDiff
from contractforge_databricks.sql import quote_identifier, quote_table_name


def render_add_columns_sql(*, target_table: str, source_schema: dict[str, str], diff: SchemaDiff) -> str:
    columns = [column for column in diff.added_columns if column in source_schema]
    if not columns:
        return "-- No additive schema changes to apply.\n"
    cols_sql = ", ".join(f"{quote_identifier(column)} {source_schema[column]}" for column in columns)
    return f"ALTER TABLE {quote_table_name(target_table)} ADD COLUMNS ({cols_sql})"


def render_type_widening_sql(*, target_table: str, diff: SchemaDiff) -> str:
    statements = [
        f"ALTER TABLE {quote_table_name(target_table)} ALTER COLUMN {quote_identifier(change.column)} TYPE {change.source_type}"
        for change in diff.type_changes
        if change.allowed
    ]
    return ";\n".join(statements) + (";\n" if statements else "-- No type widening changes to apply.\n")
