"""Databricks SQL review rendering for portable transform intent."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.sql import quote_identifier, quote_table_name


def render_transform_sql(
    contract: SemanticContract,
    *,
    source_view: str = "${prepared_source_view}",
    output_view: str = "${transformed_view}",
) -> str:
    if not contract.transform:
        return "-- No transform declared.\n"
    transform = contract.transform.raw
    select_items = _select_items(transform)
    deduplicate = transform.get("deduplicate")
    if isinstance(deduplicate, dict):
        return _render_deduplicate(
            select_items=select_items,
            source_view=source_view,
            output_view=output_view,
            deduplicate=deduplicate,
        )
    sql = [
        "-- Transform SQL review artifact.",
        "-- Databricks runtime may execute equivalent PySpark preparation for complex cases.",
        f"CREATE OR REPLACE TEMP VIEW {quote_table_name(output_view)} AS",
        "SELECT",
        ",\n".join(f"  {item}" for item in select_items),
        f"FROM {quote_table_name(source_view)}",
    ]
    return "\n".join(sql) + ";\n"


def _select_items(transform: dict[str, Any]) -> list[str]:
    items: list[str] = ["*"]
    for column, data_type in transform.get("cast", {}).items():
        items.append(f"CAST({quote_identifier(column)} AS {data_type}) AS {quote_identifier(column)}")
    for column, config in transform.get("standardize", {}).items():
        items.append(f"{_standardize_expr(column, config)} AS {quote_identifier(column)}")
    for column, expression in transform.get("derive", {}).items():
        items.append(f"{expression} AS {quote_identifier(column)}")
    for column, source_columns in transform.get("composite_keys", {}).items():
        columns = [source_columns] if isinstance(source_columns, str) else list(source_columns or ())
        parts = ", ".join(f"coalesce(CAST({quote_identifier(str(item))} AS STRING), '')" for item in columns)
        items.append(f"concat_ws('|', {parts}) AS {quote_identifier(column)}")
    return items


def _standardize_expr(column: str, config: dict[str, Any]) -> str:
    expr = quote_identifier(column)
    if config.get("normalize_whitespace"):
        expr = f"regexp_replace({expr}, '\\\\s+', ' ')"
    if config.get("trim"):
        expr = f"trim({expr})"
    if config.get("lower"):
        expr = f"lower({expr})"
    if config.get("upper"):
        expr = f"upper({expr})"
    if config.get("empty_as_null"):
        expr = f"nullif({expr}, '')"
    return expr


def _render_deduplicate(
    *,
    select_items: list[str],
    source_view: str,
    output_view: str,
    deduplicate: dict[str, Any],
) -> str:
    keys = deduplicate.get("keys")
    if isinstance(keys, str):
        key_columns = [keys]
    else:
        key_columns = [str(key) for key in keys or ()]
    order_by = _order_by(deduplicate.get("order_by"))
    partition = ", ".join(quote_identifier(column) for column in key_columns)
    lines = [
        "-- Transform SQL review artifact.",
        "-- Databricks runtime may execute equivalent PySpark preparation for complex cases.",
        f"CREATE OR REPLACE TEMP VIEW {quote_table_name(output_view)} AS",
        "WITH transformed AS (",
        "  SELECT",
        ",\n".join(f"    {item}" for item in select_items),
        f"  FROM {quote_table_name(source_view)}",
        "), ranked AS (",
        "  SELECT *,",
        f"    row_number() OVER (PARTITION BY {partition} ORDER BY {order_by}) AS __cf_row_number",
        "  FROM transformed",
        ")",
        "SELECT * EXCEPT (__cf_row_number)",
        "FROM ranked",
        "WHERE __cf_row_number = 1",
    ]
    return "\n".join(lines) + ";\n"


def _order_by(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if not isinstance(item, dict):
                continue
            clause = quote_identifier(str(item["column"]))
            clause += f" {str(item.get('direction', 'desc')).upper()}"
            if item.get("nulls"):
                clause += f" NULLS {str(item['nulls']).upper()}"
            parts.append(clause)
        return ", ".join(parts)
    raise ValueError("transform.deduplicate.order_by is required")
