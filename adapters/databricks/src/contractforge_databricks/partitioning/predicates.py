"""Databricks partition predicate rendering."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from contractforge_core.partitioning import distinct_partition_values
from contractforge_databricks.sql import quote_identifier, sql_string


def render_partition_in_predicate(column: str, values: Iterable[Any], *, max_values: int = 1000) -> str:
    distinct = distinct_partition_values(values, max_values=max_values)
    quoted = quote_identifier(column)
    non_null = [value for value in distinct if value is not None]
    predicates = []
    if non_null:
        literals = ", ".join(sql_string(value) for value in non_null)
        predicates.append(f"{quoted} IN ({literals})")
    if any(value is None for value in distinct):
        predicates.append(f"{quoted} IS NULL")
    return " OR ".join(predicates)


def render_replace_where(column: str, value: Any) -> str:
    if value is None:
        return f"{quote_identifier(column)} IS NULL"
    return f"{quote_identifier(column)} = {sql_string(value)}"
