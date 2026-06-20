"""Small SQL rendering helpers for Fabric Spark SQL."""

from __future__ import annotations


def schema_statements(schema: str, *, create_schema: bool) -> list[str]:
    return [f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(schema)};"] if create_schema else []


def delta_schema(schema: str) -> str:
    return ",\n  ".join(delta_column(column) for column in split_columns(schema))


def split_columns(schema: str) -> list[str]:
    return [column.strip() for column in schema.split(",") if column.strip()]


def delta_column(column: str) -> str:
    parts = column.split()
    if len(parts) < 2:
        raise ValueError(f"Invalid Fabric column definition: {column!r}")
    name = quote_identifier(parts[0])
    type_name = map_delta_type(parts[1])
    suffix = " ".join(parts[2:])
    return " ".join(part for part in (name, type_name, suffix) if part)


def map_delta_type(type_name: str) -> str:
    normalized = type_name.upper()
    if normalized in {"STRING", "TIMESTAMP", "DATE", "BOOLEAN", "BIGINT", "DOUBLE"}:
        return normalized
    raise ValueError(f"Unsupported column type for Fabric Lakehouse Delta: {type_name}")


def quote_table_name(value: str) -> str:
    return ".".join(quote_identifier(part) for part in value.split("."))


def quote_identifier(value: str | None) -> str:
    if value is None:
        raise ValueError("identifier is required")
    text = str(value).strip()
    if not text:
        raise ValueError("identifier must not be empty")
    return f"`{text.replace('`', '``')}`"


def sql_string(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def sql_int(value: object) -> str:
    return "NULL" if value is None else str(int(value))


def sql_bool(value: object) -> str:
    return "TRUE" if bool(value) else "FALSE"


__all__ = [
    "delta_column",
    "delta_schema",
    "map_delta_type",
    "quote_identifier",
    "quote_table_name",
    "schema_statements",
    "sql_bool",
    "sql_int",
    "sql_string",
    "split_columns",
]
