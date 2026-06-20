"""Portable logical table reference helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable


TableRefResolver = Callable[["LogicalTableReference"], str]

_TABLE_REF_PATTERN = re.compile(r"\{\{\s*table_ref:([A-Za-z][A-Za-z0-9_-]*\.[A-Za-z][A-Za-z0-9_-]*)\s*\}\}")
_REF_PART_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class LogicalTableReference:
    """Platform-neutral reference to a contract-managed table."""

    layer: str
    table: str
    schema: str | None = None
    catalog: str | None = None

    @property
    def key(self) -> str:
        return f"{self.layer}.{self.table}"


def parse_logical_table_reference(value: str | dict[str, Any]) -> LogicalTableReference:
    """Parse ``layer.table`` or ``{layer, table}`` into a logical reference."""

    if isinstance(value, str):
        parts = value.strip().split(".")
        if len(parts) != 2:
            raise ValueError("logical table reference strings must use 'layer.table'")
        layer, table = parts
        return _validated_ref(layer=layer, table=table)
    if isinstance(value, dict):
        layer = value.get("layer")
        table = value.get("table")
        if not layer or not table:
            raise ValueError("logical table reference mappings require layer and table")
        return _validated_ref(
            layer=str(layer),
            table=str(table),
            schema=str(value["schema"]) if value.get("schema") else None,
            catalog=str(value["catalog"]) if value.get("catalog") else None,
        )
    raise ValueError("logical table reference must be a 'layer.table' string or a mapping")


def source_logical_table_reference(source: dict[str, Any]) -> LogicalTableReference | None:
    """Return a table reference declared directly on a source, if present."""

    value = source.get("table_ref") or source.get("ref")
    return parse_logical_table_reference(value) if value else None


def render_table_reference_placeholders(query: str, resolver: TableRefResolver) -> str:
    """Replace ``{{ table_ref:layer.table }}`` placeholders in a SQL string."""

    def _replace(match: re.Match[str]) -> str:
        return resolver(parse_logical_table_reference(match.group(1)))

    return _TABLE_REF_PATTERN.sub(_replace, query)


def has_table_reference_placeholders(query: str) -> bool:
    return bool(_TABLE_REF_PATTERN.search(query))


def _validated_ref(
    *,
    layer: str,
    table: str,
    schema: str | None = None,
    catalog: str | None = None,
) -> LogicalTableReference:
    for label, value in (("layer", layer), ("table", table)):
        if not _REF_PART_RE.match(value):
            raise ValueError(f"logical table reference {label} must start with a letter and contain only letters, numbers, '_' or '-'")
    return LogicalTableReference(layer=layer, table=table, schema=schema, catalog=catalog)
