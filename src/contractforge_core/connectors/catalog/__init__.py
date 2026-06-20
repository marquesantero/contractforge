"""Facade for the catalog connector family."""

from contractforge_core.connectors.catalog.catalog import (
    CATALOG_SOURCE_TYPES,
    LogicalTableReference,
    TableRefResolver,
    catalog_source_query,
    catalog_source_table_or_path,
    has_table_reference_placeholders,
    is_catalog_source,
    parse_logical_table_reference,
    render_table_reference_placeholders,
    source_logical_table_reference,
)

__all__ = [
    "CATALOG_SOURCE_TYPES",
    "LogicalTableReference",
    "TableRefResolver",
    "catalog_source_query",
    "catalog_source_table_or_path",
    "has_table_reference_placeholders",
    "is_catalog_source",
    "parse_logical_table_reference",
    "render_table_reference_placeholders",
    "source_logical_table_reference",
]
