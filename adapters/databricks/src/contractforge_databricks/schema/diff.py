"""Compatibility exports for platform-neutral schema diff helpers."""

from contractforge_core.schema import SchemaDiff, TypeChange, compare_schema, is_type_widening, validate_schema_diff

__all__ = [
    "SchemaDiff",
    "TypeChange",
    "compare_schema",
    "is_type_widening",
    "validate_schema_diff",
]
