"""Databricks SQL quality check rendering."""

from __future__ import annotations

from contractforge_core.config import MAX_INLINE_ACCEPTED_VALUES
from contractforge_core.semantic import QualityIntent, SemanticContract
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_identifier, quote_table_name


def render_quality_check_sql(contract: SemanticContract, *, source_view: str | None = None) -> str:
    table = quote_table_name(source_view or target_full_name(contract))
    statements = []
    for quality in contract.quality:
        statements.append(_render_quality_intent(quality, table))
    return "\n\n".join(statements) + ("\n" if statements else "-- No quality rules declared.\n")


def _render_quality_intent(quality: QualityIntent, table: str) -> str:
    if quality.rule == "required_columns":
        return _render_required_columns(quality, table)
    if quality.rule == "not_null":
        column = _single_column(quality)
        return (
            f"-- quality: {quality.name}\n"
            f"SELECT count(*) AS failed_rows FROM {table} WHERE {quote_identifier(column)} IS NULL;"
        )
    if quality.rule == "unique_key":
        keys = ", ".join(quote_identifier(column) for column in quality.columns)
        return (
            f"-- quality: {quality.name}\n"
            f"SELECT count(*) AS failed_rows FROM ("
            f"SELECT {keys}, count(*) AS row_count FROM {table} GROUP BY {keys} HAVING count(*) > 1"
            ") duplicates;"
        )
    if quality.rule == "accepted_values":
        column = _single_column(quality)
        values = quality.value if isinstance(quality.value, (list, tuple)) else [quality.value]
        if len(values) > MAX_INLINE_ACCEPTED_VALUES:
            raise ValueError(
                f"quality.accepted_values.{column} has {len(values)} values. "
                "Use a reference table or custom quality evaluator for large value sets."
            )
        accepted = ", ".join(_sql_literal(value) for value in values)
        return (
            f"-- quality: {quality.name}\n"
            f"SELECT count(*) AS failed_rows FROM {table} "
            f"WHERE {quote_identifier(column)} IS NOT NULL AND {quote_identifier(column)} NOT IN ({accepted});"
        )
    if quality.rule == "row_count_minimum":
        return (
            f"-- quality: {quality.name}\n"
            f"SELECT CASE WHEN count(*) >= {int(quality.value)} THEN 0 ELSE 1 END AS failed_rows FROM {table};"
        )
    if quality.rule == "max_null_ratio":
        column = _single_column(quality)
        ratio = float(quality.value)
        return (
            f"-- quality: {quality.name}\n"
            "SELECT CASE WHEN count(*) = 0 THEN 0 "
            f"WHEN (sum(CASE WHEN {quote_identifier(column)} IS NULL THEN 1 ELSE 0 END) / count(*)) > {ratio} "
            "THEN 1 ELSE 0 END AS failed_rows "
            f"FROM {table};"
        )
    if quality.rule == "expression":
        return (
            f"-- quality: {quality.name}\n"
            f"SELECT count(*) AS failed_rows FROM {table} "
            f"WHERE NOT ({quality.value}) OR ({quality.value}) IS NULL;"
        )
    return f"-- Unsupported quality rule for Databricks SQL rendering: {quality.rule}\n"


def _single_column(quality: QualityIntent) -> str:
    if len(quality.columns) != 1:
        raise ValueError(f"quality rule {quality.name} requires exactly one column")
    return quality.columns[0]


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _render_required_columns(quality: QualityIntent, table: str) -> str:
    parts = _unquote_table_parts(table)
    expected = ", ".join(_sql_literal(column) for column in quality.columns)
    if len(parts) != 3:
        return (
            f"-- quality: {quality.name}\n"
            "-- Required column checks need runtime schema inspection for temp views or non-qualified tables.\n"
            f"-- expected columns: {', '.join(quality.columns)}"
        )
    catalog, schema, table_name = parts
    return (
        f"-- quality: {quality.name}\n"
        f"SELECT count(*) AS failed_rows FROM (SELECT explode(array({expected})) AS expected_column) expected "
        "LEFT ANTI JOIN ("
        "SELECT column_name FROM system.information_schema.columns "
        f"WHERE table_catalog = {_sql_literal(catalog)} "
        f"AND table_schema = {_sql_literal(schema)} "
        f"AND table_name = {_sql_literal(table_name)}"
        ") actual ON expected.expected_column = actual.column_name;"
    )


def _unquote_table_parts(table: str) -> tuple[str, ...]:
    return tuple(part.strip("`").replace("``", "`") for part in table.split(".") if part.strip("`"))
