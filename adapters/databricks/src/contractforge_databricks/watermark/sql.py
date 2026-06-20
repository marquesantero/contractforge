"""Databricks SQL helpers for ContractForge typed watermarks."""

from __future__ import annotations

from contractforge_core.watermark import decode_watermark_value
from contractforge_databricks.sql import quote_identifier, quote_table_name, sql_string


def render_watermark_filter_predicate(*, columns: tuple[str, ...], watermark_value: str | None) -> str:
    """Render a lexicographic SQL predicate for rows after a typed watermark."""
    if not columns or not watermark_value:
        return "true"
    decoded = decode_watermark_value(watermark_value, columns)
    if not decoded:
        return "true"
    if len(columns) == 1:
        column = columns[0]
        return f"{quote_identifier(column)} > {_typed_literal(decoded[column].value, decoded[column].type)}"

    branches: list[str] = []
    for index, column in enumerate(columns):
        comparisons = [
            f"{quote_identifier(previous)} = {_typed_literal(decoded[previous].value, decoded[previous].type)}"
            for previous in columns[:index]
        ]
        comparisons.append(
            f"{quote_identifier(column)} > {_typed_literal(decoded[column].value, decoded[column].type)}"
        )
        branches.append("(" + " AND ".join(comparisons) + ")")
    return "(" + " OR ".join(branches) + ")"


def render_select_watermark_candidate_sql(
    *,
    table_name: str,
    columns: tuple[str, ...],
    types: dict[str, str] | None = None,
) -> str:
    """Render SQL that computes the next typed watermark candidate from a table."""
    if not columns:
        raise ValueError("watermark columns must not be empty")
    type_map = types or {}
    if len(columns) == 1:
        column = columns[0]
        return "\n".join(
            [
                "SELECT",
                f"  to_json(named_struct({sql_string(column)}, named_struct(",
                f"    'type', {sql_string(type_map.get(column, 'string'))},",
                f"    'value', CAST(MAX({quote_identifier(column)}) AS STRING)",
                "  ))) AS watermark_value",
                f"FROM {quote_table_name(table_name)}",
            ]
        )

    struct_fields = ", ".join(
        f"{sql_string(column)}, {quote_identifier(column)}" for column in columns
    )
    json_fields = _candidate_json_fields(columns, type_map)
    return "\n".join(
        [
            "WITH candidate AS (",
            f"  SELECT MAX(named_struct({struct_fields})) AS wm",
            f"  FROM {quote_table_name(table_name)}",
            ")",
            "SELECT",
            f"  to_json(named_struct({json_fields})) AS watermark_value",
            "FROM candidate",
        ]
    )


def _candidate_json_fields(columns: tuple[str, ...], types: dict[str, str]) -> str:
    fields = []
    for column in columns:
        fields.append(
            ", ".join(
                [
                    sql_string(column),
                    "named_struct("
                    f"'type', {sql_string(types.get(column, 'string'))}, "
                    f"'value', CAST(wm.{quote_identifier(column)} AS STRING)"
                    ")",
                ]
            )
        )
    return ", ".join(fields)


def _typed_literal(value: str | None, data_type: str) -> str:
    return f"CAST({sql_string(value)} AS {data_type})"
