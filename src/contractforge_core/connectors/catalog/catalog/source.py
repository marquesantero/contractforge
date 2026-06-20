"""Catalog source helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors.catalog.catalog.table_refs import (
    TableRefResolver,
    render_table_reference_placeholders,
    source_logical_table_reference,
)

CATALOG_SOURCE_TYPES = frozenset({"table", "delta_table", "iceberg_table", "view", "sql"})


def is_catalog_source(source: dict[str, Any]) -> bool:
    return source.get("type") in CATALOG_SOURCE_TYPES or source.get("connector") in CATALOG_SOURCE_TYPES


def catalog_source_table_or_path(source: dict[str, Any], *, table_ref_resolver: TableRefResolver | None = None) -> str:
    table_ref = source_logical_table_reference(source)
    if table_ref is not None:
        if table_ref_resolver is None:
            raise ValueError("catalog source logical table references require an adapter table_ref_resolver")
        return table_ref_resolver(table_ref)
    table = source.get("table") or source.get("path")
    if not table:
        raise ValueError("catalog source requires table, path or ref/table_ref")
    return str(table)


def catalog_source_query(source: dict[str, Any], *, table_ref_resolver: TableRefResolver | None = None) -> str:
    query = source.get("query") or source.get("options", {}).get("query")
    if not query:
        raise ValueError("sql source requires query or options.query")
    sql = str(query)
    if table_ref_resolver is None:
        return sql
    return render_table_reference_placeholders(sql, table_ref_resolver)
