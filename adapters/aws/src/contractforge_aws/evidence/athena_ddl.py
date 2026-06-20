"""Athena Iceberg DDL for ContractForge evidence tables."""

from __future__ import annotations

import re

from contractforge_core.evidence import EVIDENCE_TABLES, EVIDENCE_TABLE_SCHEMAS, STATE_TABLES, STATE_TABLE_SCHEMAS

from contractforge_aws.evidence.ddl import _PARTITION_COLUMNS

_SAFE_ATHENA_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def render_create_evidence_tables_athena_sql(
    *,
    database: str = "contractforge_ops",
    warehouse_uri: str,
) -> str:
    """Render Athena-compatible Iceberg DDL for evidence tables."""

    statements = [f"CREATE DATABASE IF NOT EXISTS {_quote_athena_database(database)};"]
    for name, table in EVIDENCE_TABLES.items():
        partition = _PARTITION_COLUMNS.get(name)
        partition_sql = f"\nPARTITIONED BY ({_quote_athena_identifier(partition)})" if partition else ""
        statements.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {_athena_table(database, table)} (",
                    f"  {_athena_schema(EVIDENCE_TABLE_SCHEMAS[name])}",
                    f"){partition_sql}",
                    f"LOCATION {_quote_sql_string(_table_location(warehouse_uri, database, table))}",
                    "TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet');",
                ]
            )
        )
    return "\n\n".join(statements) + "\n"


def render_create_state_tables_athena_sql(
    *,
    database: str = "contractforge_ops",
    warehouse_uri: str,
) -> str:
    """Render Athena-compatible Iceberg DDL for state tables."""

    statements = [f"CREATE DATABASE IF NOT EXISTS {_quote_athena_database(database)};"]
    for name, table in STATE_TABLES.items():
        statements.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {_athena_table(database, table)} (",
                    f"  {_athena_schema(STATE_TABLE_SCHEMAS[name])}",
                    ")",
                    f"LOCATION {_quote_sql_string(_table_location(warehouse_uri, database, table))}",
                    "TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet');",
                ]
            )
        )
    return "\n\n".join(statements) + "\n"


def _athena_schema(schema: str) -> str:
    columns = [_athena_column(column) for column in _split_columns(schema)]
    return ",\n  ".join(columns)


def _split_columns(schema: str) -> list[str]:
    return [column.strip() for column in schema.split(",") if column.strip()]


def _athena_column(column: str) -> str:
    parts = column.split()
    if len(parts) < 2:
        raise ValueError(f"Invalid evidence column definition: {column!r}")
    name = _quote_athena_identifier(parts[0])
    type_name = _map_athena_type(parts[1])
    return f"{name} {type_name}"


def _map_athena_type(type_name: str) -> str:
    normalized = type_name.upper()
    mapping = {
        "STRING": "STRING",
        "TIMESTAMP": "TIMESTAMP",
        "DATE": "DATE",
        "BOOLEAN": "BOOLEAN",
        "BIGINT": "BIGINT",
        "DOUBLE": "DOUBLE",
    }
    if normalized not in mapping:
        raise ValueError(f"Unsupported evidence column type for Athena Iceberg: {type_name}")
    return mapping[normalized]


def _quote_athena_identifier(value: str | None) -> str:
    if value is None:
        raise ValueError("identifier is required")
    text = str(value).strip()
    if not text:
        raise ValueError("identifier must not be empty")
    if not _SAFE_ATHENA_IDENTIFIER.fullmatch(text):
        raise ValueError(f"Athena Iceberg identifier must be alphanumeric or underscore: {text!r}")
    return text


def _quote_athena_database(value: str | None) -> str:
    if value is None:
        raise ValueError("identifier is required")
    text = str(value).strip()
    if not text:
        raise ValueError("identifier must not be empty")
    if text[0].isdigit() or not text.replace("_", "").isalnum():
        return '"' + text.replace('"', '""') + '"'
    return text


def _quote_sql_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _athena_table(database: str, table: str) -> str:
    return f"{_quote_athena_identifier(database)}.{_quote_athena_identifier(table)}"


def _table_location(warehouse_uri: str, database: str, table: str) -> str:
    base = str(warehouse_uri or "").strip().rstrip("/")
    if not base.startswith("s3://"):
        raise ValueError("Athena evidence warehouse_uri must be an s3:// URI")
    return f"{base}/{_path_segment(database)}.db/{_path_segment(table)}/"


def _path_segment(value: str) -> str:
    return str(value).strip().replace("/", "_").replace("\\", "_")
