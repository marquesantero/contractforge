"""Snowflake schema-policy checks for runtime execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.security.redaction import redact_text
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.session_ops import execute, row_value
from contractforge_snowflake.sql import sql_string


@dataclass(frozen=True)
class SnowflakeSchemaPolicyResult:
    commands: tuple[str, ...]
    source_columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    schema_changes: dict[str, Any]


@dataclass(frozen=True)
class _TargetSchemaInspection:
    column_types: dict[str, str]
    warning: str | None = None
    missing: bool = False


def enforce_schema_policy(
    *,
    session: Any,
    contract: SemanticContract,
    source_sql: str,
    target: str,
) -> SnowflakeSchemaPolicyResult:
    source_types = source_column_types_for(session, source_sql)
    source_columns = tuple(source_types)
    if contract.write.schema_policy == "permissive":
        return SnowflakeSchemaPolicyResult(commands=(), source_columns=source_columns, target_columns=(), schema_changes={})
    target_inspection = _target_column_types_with_diagnostics(session, target)
    target_types = target_inspection.column_types
    inspection_warning = target_inspection.warning
    if target_inspection.missing and contract.write.mode in {"overwrite", "scd0_overwrite"}:
        return SnowflakeSchemaPolicyResult(
            commands=(),
            source_columns=source_columns,
            target_columns=source_columns,
            schema_changes=_schema_changes(
                added=(),
                removed=(),
                type_changes=(),
                source_types=source_types,
                target_types={},
                applied_additions=set(),
                inspection_warning=inspection_warning or "target_missing_initial_overwrite_create",
            ),
        )
    target_columns = tuple(target_types)
    source_set = set(source_columns)
    target_set = set(target_columns)
    removed = tuple(column for column in target_columns if column not in source_set)
    added = tuple(column for column in source_columns if column not in target_set)
    type_changes = _type_changes(source_types=source_types, target_types=target_types)
    incompatible = tuple(change for change in type_changes if change["classification"] == "INCOMPATIBLE")
    if contract.write.schema_policy == "strict" and (added or removed):
        raise ValueError(f"Snowflake strict schema policy violation: added={added}, removed={removed}")
    if incompatible:
        raise ValueError(f"Snowflake {contract.write.schema_policy} schema policy incompatible type changes: {incompatible}")
    if contract.write.schema_policy == "additive_only" and removed:
        raise ValueError(f"Snowflake additive_only schema policy violation: removed={removed}")
    commands: tuple[str, ...] = ()
    if contract.write.schema_policy == "additive_only" and added:
        commands = tuple(_add_column_sql(target, column, source_types[column]) for column in added)
        for command in commands:
            execute(session, command)
    schema_changes = _schema_changes(
        added=added,
        removed=removed,
        type_changes=type_changes,
        source_types=source_types,
        target_types=target_types,
        applied_additions=set(added) if contract.write.schema_policy == "additive_only" else set(),
        inspection_warning=inspection_warning,
    )
    return SnowflakeSchemaPolicyResult(
        commands=commands,
        source_columns=source_columns,
        target_columns=(*target_columns, *added),
        schema_changes=schema_changes,
    )


def source_columns_for(session: Any, source_sql: str) -> tuple[str, ...]:
    return tuple(source_column_types_for(session, source_sql))


def source_column_types_for(session: Any, source_sql: str) -> dict[str, str]:
    result = session.sql(f"SELECT * FROM (\n{source_sql}\n) AS _CF_SOURCE LIMIT 0")
    return _schema_types(result)


def target_columns_for(session: Any, target: str) -> tuple[str, ...]:
    return tuple(target_column_types_for(session, target))


def target_column_types_for(session: Any, target: str) -> dict[str, str]:
    info_schema, _warning = _target_column_types_from_information_schema(session, target)
    if info_schema:
        return info_schema
    result = session.sql(f"SELECT * FROM {target} LIMIT 0")
    return _schema_types(result)


def _target_column_types_with_diagnostics(session: Any, target: str) -> _TargetSchemaInspection:
    info_schema, warning = _target_column_types_from_information_schema(session, target)
    if info_schema:
        return _TargetSchemaInspection(info_schema)
    try:
        result = session.sql(f"SELECT * FROM {target} LIMIT 0")
    except Exception as exc:
        text = redact_text(str(exc))
        missing = _is_missing_target_error(exc)
        return _TargetSchemaInspection(
            {},
            warning or f"target_schema_unavailable: {type(exc).__name__}: {text}",
            missing=missing,
        )
    try:
        return _TargetSchemaInspection(_schema_types(result), warning)
    except Exception as exc:
        text = redact_text(str(exc))
        missing = _is_missing_target_error(exc)
        return _TargetSchemaInspection(
            {},
            warning or f"target_schema_unavailable: {type(exc).__name__}: {text}",
            missing=missing,
        )


def _is_missing_target_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "does not exist" in text or "42s02" in text or ("object" in text and "not authorized" in text)


def _target_column_types_from_information_schema(session: Any, target: str) -> tuple[dict[str, str], str | None]:
    parts = _split_identifier(target)
    if len(parts) != 3:
        return {}, None
    database, schema, table = parts
    command = (
        f"SELECT COLUMN_NAME, DATA_TYPE FROM {quote_identifier(database)}.INFORMATION_SCHEMA.COLUMNS\n"
        f"WHERE TABLE_SCHEMA = {sql_string(schema)} AND TABLE_NAME = {sql_string(table)}\n"
        "ORDER BY ORDINAL_POSITION"
    )
    try:
        rows = session.sql(command).collect()
    except Exception as exc:
        return {}, f"information_schema_unavailable: {type(exc).__name__}: {redact_text(str(exc))}"
    return (
        {
            _normalize_schema_column_name(str(row_value(row, 0, "COLUMN_NAME"))): _normalize_snowflake_type(str(row_value(row, 1, "DATA_TYPE")))
            for row in rows
            if row_value(row, 0, "COLUMN_NAME") is not None
        },
        None,
    )


def _schema_names(result: Any) -> tuple[str, ...]:
    return tuple(_schema_types(result))


def _schema_types(result: Any) -> dict[str, str]:
    schema = getattr(result, "schema", None)
    fields = getattr(schema, "fields", None)
    if fields:
        return {_normalize_schema_column_name(str(getattr(field, "name"))): _snowflake_type(field) for field in fields}
    names = getattr(schema, "names", None)
    if names:
        return {_normalize_schema_column_name(str(name)): "VARIANT" for name in names}
    raise ValueError("Snowflake session result schema does not expose column names")


def _normalize_schema_column_name(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1].replace('""', '"')
    return text


def _snowflake_type(field: Any) -> str:
    for attribute in ("datatype", "data_type", "type", "type_name"):
        value = getattr(field, attribute, None)
        if value is not None:
            return _normalize_snowflake_type(str(value))
    raise ValueError(f"Snowflake source column {getattr(field, 'name', '<unknown>')!r} does not expose a data type")


def _normalize_snowflake_type(value: str) -> str:
    text = value.upper().replace("()", "").strip()
    if text.startswith("STRINGTYPE"):
        return "VARCHAR"
    if text.startswith("DECIMALTYPE") or text.startswith("LONGTYPE") or text.startswith("INTEGERTYPE"):
        return "NUMBER"
    if text.startswith("DOUBLETYPE") or text.startswith("FLOATTYPE"):
        return "FLOAT"
    if text.startswith("BOOLEANTYPE"):
        return "BOOLEAN"
    if text.startswith("DATETYPE"):
        return "DATE"
    if text.startswith("TIMESTAMPTYPE"):
        if "'LTZ'" in text or '"LTZ"' in text:
            return "TIMESTAMP_LTZ"
        if "'TZ'" in text or '"TZ"' in text:
            return "TIMESTAMP_TZ"
        return "TIMESTAMP_NTZ"
    numeric_aliases = {
        "0": "NUMBER",
        "1": "FLOAT",
        "2": "VARCHAR",
        "3": "DATE",
        "4": "TIMESTAMP_NTZ",
        "5": "VARIANT",
        "6": "TIMESTAMP_NTZ",
        "7": "TIMESTAMP_NTZ",
        "8": "TIMESTAMP_NTZ",
        "9": "OBJECT",
        "10": "ARRAY",
        "11": "BINARY",
        "12": "TIME",
        "13": "BOOLEAN",
    }
    if text.isdigit():
        return numeric_aliases.get(text, "VARIANT")
    aliases = {
        "STRING": "VARCHAR",
        "STR": "VARCHAR",
        "TEXT": "VARCHAR",
        "INTEGER": "NUMBER",
        "INT": "NUMBER",
        "LONG": "NUMBER",
        "DOUBLE": "FLOAT",
        "DOUBLETYPE": "FLOAT",
        "FLOATTYPE": "FLOAT",
        "BOOLEANTYPE": "BOOLEAN",
        "STRINGTYPE": "VARCHAR",
        "INTEGERTYPE": "NUMBER",
        "LONGTYPE": "NUMBER",
        "TIMESTAMP": "TIMESTAMP_NTZ",
        "TIMESTAMPTYPE": "TIMESTAMP_NTZ",
        "DATE": "DATE",
        "DATETYPE": "DATE",
        "VARIANT": "VARIANT",
    }
    return aliases.get(text, text)


def _type_changes(*, source_types: dict[str, str], target_types: dict[str, str]) -> tuple[dict[str, str], ...]:
    changes: list[dict[str, str]] = []
    for column in tuple(column for column in source_types if column in target_types):
        source_type = _normalize_snowflake_type(source_types[column])
        target_type = _normalize_snowflake_type(target_types[column])
        if source_type == target_type:
            continue
        if "VARIANT" in {source_type, target_type}:
            continue
        changes.append(
            {
                "column": column,
                "source_type": source_type,
                "target_type": target_type,
                "classification": _type_change_classification(source_type=source_type, target_type=target_type),
            }
        )
    return tuple(changes)


def _type_change_classification(*, source_type: str, target_type: str) -> str:
    if _type_family(source_type) != _type_family(target_type):
        return "INCOMPATIBLE"
    return "WIDENING"


def _type_family(data_type: str) -> str:
    return _normalize_snowflake_type(data_type).split("(", 1)[0]


def _schema_changes(
    *,
    added: tuple[str, ...],
    removed: tuple[str, ...],
    type_changes: tuple[dict[str, str], ...],
    source_types: dict[str, str],
    target_types: dict[str, str],
    applied_additions: set[str],
    inspection_warning: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if inspection_warning:
        payload["warnings"] = (inspection_warning,)
    if added:
        payload["added_columns"] = tuple(
            {
                "column": column,
                "source_type": source_types[column],
                "target_type": None,
                "change_type": "ADD_COLUMN",
                "applied": column in applied_additions,
            }
            for column in added
        )
    if removed:
        payload["removed_columns"] = tuple(
            {
                "column": column,
                "source_type": None,
                "target_type": target_types[column],
                "change_type": "REMOVE_COLUMN",
                "applied": False,
            }
            for column in removed
        )
    if type_changes:
        payload["type_changes"] = tuple(
            {
                **change,
                "change_type": "TYPE_CHANGE",
                "applied": False,
            }
            for change in type_changes
        )
    return payload


def _add_column_sql(target: str, column: str, data_type: str) -> str:
    return f"ALTER TABLE {target} ADD COLUMN IF NOT EXISTS {quote_identifier(column)} {data_type}"


def _split_identifier(value: str) -> tuple[str, ...]:
    parts: list[str] = []
    current: list[str] = []
    quoted = False
    index = 0
    while index < len(value):
        char = value[index]
        if char == '"':
            if quoted and index + 1 < len(value) and value[index + 1] == '"':
                current.append('"')
                index += 2
                continue
            quoted = not quoted
            index += 1
            continue
        if char == "." and not quoted:
            parts.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    parts.append("".join(current))
    return tuple(part for part in parts if part)


__all__ = [
    "SnowflakeSchemaPolicyResult",
    "enforce_schema_policy",
    "source_column_types_for",
    "source_columns_for",
    "target_column_types_for",
    "target_columns_for",
]
