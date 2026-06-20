"""Platform-neutral schema diff and policy validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from contractforge_core.config import CONTROL_COLUMNS
from contractforge_core.semantic import SchemaPolicy

LEGACY_PHYSICAL_METADATA_COLUMNS = frozenset({"ingestion_date", "source_system", "ingestion_sequence"})
IGNORED_TARGET_ONLY_COLUMNS = frozenset(CONTROL_COLUMNS) | LEGACY_PHYSICAL_METADATA_COLUMNS
INTEGER_ORDER = {"tinyint": 0, "smallint": 1, "int": 2, "bigint": 3}
FLOAT_ORDER = {"float": 0, "double": 1}


@dataclass(frozen=True)
class TypeChange:
    column: str
    source_type: str
    target_type: str
    allowed: bool
    change: str

    def as_dict(self) -> dict[str, object]:
        return {
            "column": self.column,
            "source": self.source_type,
            "target": self.target_type,
            "allowed": self.allowed,
            "change": self.change,
        }


@dataclass(frozen=True)
class SchemaDiff:
    status: str
    added_columns: tuple[str, ...]
    removed_columns: tuple[str, ...]
    type_changes: tuple[TypeChange, ...]
    allow_type_widening: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "added_columns": list(self.added_columns),
            "removed_columns": list(self.removed_columns),
            "type_changes": [change.as_dict() for change in self.type_changes],
            "allow_type_widening": self.allow_type_widening,
        }


def compare_schema(
    source_schema: dict[str, str],
    target_schema: dict[str, str] | None,
    *,
    allow_type_widening: bool = False,
) -> SchemaDiff:
    if target_schema is None:
        return SchemaDiff("new_table", (), (), (), allow_type_widening)
    added = tuple(sorted(column for column in source_schema if column not in target_schema))
    removed = tuple(
        sorted(column for column in target_schema if column not in source_schema and column not in IGNORED_TARGET_ONLY_COLUMNS)
    )
    changes = tuple(
        _type_change(column, source_schema[column], target_schema[column], allow_type_widening)
        for column in sorted(source_schema.keys() & target_schema.keys())
        if source_schema[column] != target_schema[column]
    )
    return SchemaDiff("checked", added, removed, changes, allow_type_widening)


def validate_schema_diff(diff: SchemaDiff, policy: SchemaPolicy) -> SchemaDiff:
    blocking_type_changes = tuple(change for change in diff.type_changes if not change.allowed)
    if policy == "strict" and (diff.added_columns or diff.removed_columns or diff.type_changes):
        raise ValueError(
            "Schema policy strict violation: "
            f"added={list(diff.added_columns)}, removed={list(diff.removed_columns)}, "
            f"type_changes={[change.as_dict() for change in diff.type_changes]}"
        )
    if policy == "additive_only" and (diff.removed_columns or blocking_type_changes):
        raise ValueError(
            "Schema policy additive_only violation: "
            f"removed={list(diff.removed_columns)}, "
            f"type_changes={[change.as_dict() for change in blocking_type_changes]}"
        )
    if policy == "permissive" and blocking_type_changes:
        raise ValueError(
            "Schema policy permissive does not apply potentially destructive type changes. "
            f"type_changes={[change.as_dict() for change in blocking_type_changes]}"
        )
    return diff


def is_type_widening(source_type: str, target_type: str) -> bool:
    source_type = str(source_type).strip().lower()
    target_type = str(target_type).strip().lower()
    if source_type == target_type:
        return True
    if source_type in INTEGER_ORDER and target_type in INTEGER_ORDER:
        return INTEGER_ORDER[source_type] >= INTEGER_ORDER[target_type]
    if source_type in FLOAT_ORDER and target_type in FLOAT_ORDER:
        return FLOAT_ORDER[source_type] >= FLOAT_ORDER[target_type]
    if source_type == "double" and target_type in INTEGER_ORDER:
        return True
    if source_type == "timestamp" and target_type == "date":
        return True
    source_decimal = _decimal_parts(source_type)
    target_decimal = _decimal_parts(target_type)
    if source_decimal and target_decimal:
        return source_decimal[0] >= target_decimal[0] and source_decimal[1] >= target_decimal[1]
    return False


def _type_change(column: str, source_type: str, target_type: str, allow_type_widening: bool) -> TypeChange:
    allowed = allow_type_widening and is_type_widening(source_type, target_type)
    return TypeChange(column, source_type, target_type, allowed, "type_widening" if allowed else "type_change")


def _decimal_parts(dtype: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"decimal\((\d+),(\d+)\)", dtype)
    return (int(match.group(1)), int(match.group(2))) if match else None
