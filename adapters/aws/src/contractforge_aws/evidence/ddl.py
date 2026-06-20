"""AWS Iceberg DDL for ContractForge evidence tables."""

from __future__ import annotations

from contractforge_core.evidence import EVIDENCE_TABLES, EVIDENCE_TABLE_SCHEMAS, STATE_TABLES, STATE_TABLE_SCHEMAS

_PARTITION_COLUMNS = {
    "runs": "run_date",
    "errors": "error_date",
    "deployments": "deployment_date",
}


def evidence_table_names(database: str = "contractforge_ops") -> dict[str, str]:
    return {name: f"glue_catalog.{_quote_identifier(database)}.{_quote_identifier(table)}" for name, table in EVIDENCE_TABLES.items()}


def state_table_names(database: str = "contractforge_ops") -> dict[str, str]:
    return {name: f"glue_catalog.{_quote_identifier(database)}.{_quote_identifier(table)}" for name, table in STATE_TABLES.items()}


def render_create_evidence_tables_sql(*, database: str = "contractforge_ops") -> str:
    table_names = evidence_table_names(database)
    statements = [f"CREATE DATABASE IF NOT EXISTS glue_catalog.{_quote_identifier(database)};"]
    for name, table in table_names.items():
        partition = _PARTITION_COLUMNS.get(name)
        partition_sql = f"\nPARTITIONED BY ({_quote_identifier(partition)})" if partition else ""
        statements.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {table} (",
                    f"  {_iceberg_schema(EVIDENCE_TABLE_SCHEMAS[name])}",
                    ")",
                    f"USING iceberg{partition_sql};",
                ]
            )
        )
    return "\n\n".join(statements) + "\n"


def render_evidence_table_ddl(name: str, database: str = "contractforge_ops") -> str:
    """Render a single CREATE TABLE IF NOT EXISTS for one evidence table (no trailing ;)."""

    table = evidence_table_names(database)[name]
    partition = _PARTITION_COLUMNS.get(name)
    lines = [
        f"CREATE TABLE IF NOT EXISTS {table} (",
        f"  {_iceberg_schema(EVIDENCE_TABLE_SCHEMAS[name])}",
        ")",
        "USING iceberg",
    ]
    if partition:
        lines.append(f"PARTITIONED BY ({_quote_identifier(partition)})")
    return "\n".join(lines)


def render_runs_table_ddl(database: str = "contractforge_ops") -> str:
    """Render a single CREATE TABLE IF NOT EXISTS for the runs control table (no trailing ;)."""

    return render_evidence_table_ddl("runs", database)


def render_create_state_tables_sql(*, database: str = "contractforge_ops") -> str:
    names = state_table_names(database)
    statements = [f"CREATE DATABASE IF NOT EXISTS glue_catalog.{_quote_identifier(database)};"]
    for name, table in names.items():
        statements.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {table} (",
                    f"  {_iceberg_schema(STATE_TABLE_SCHEMAS[name])}",
                    ")",
                    "USING iceberg;",
                ]
            )
        )
    return "\n\n".join(statements) + "\n"


def render_state_table_ddl(name: str, database: str = "contractforge_ops") -> str:
    """Render a single CREATE TABLE IF NOT EXISTS for one state table (no trailing ;)."""

    table = state_table_names(database)[name]
    return "\n".join(
        [
            f"CREATE TABLE IF NOT EXISTS {table} (",
            f"  {_iceberg_schema(STATE_TABLE_SCHEMAS[name])}",
            ")",
            "USING iceberg",
        ]
    )


def render_evidence_table_notes(*, database: str = "contractforge_ops") -> str:
    lines = [
        "-- AWS evidence table mapping.",
        "-- These tables preserve the core ContractForge evidence/control table schema.",
        "-- Persistence target: Apache Iceberg tables registered in AWS Glue Catalog.",
        "",
    ]
    for name, table in evidence_table_names(database).items():
        lines.append(f"-- {name}: {table}")
    for name, table in state_table_names(database).items():
        lines.append(f"-- {name}: {table}")
    return "\n".join(lines) + "\n"


def _iceberg_schema(schema: str) -> str:
    columns = [_iceberg_column(column) for column in _split_columns(schema)]
    return ",\n  ".join(columns)


def _split_columns(schema: str) -> list[str]:
    return [column.strip() for column in schema.split(",") if column.strip()]


def _iceberg_column(column: str) -> str:
    parts = column.split()
    if len(parts) < 2:
        raise ValueError(f"Invalid evidence column definition: {column!r}")
    name = _quote_identifier(parts[0])
    type_name = _map_type(parts[1])
    suffix = " ".join(parts[2:])
    return " ".join(part for part in (name, type_name, suffix) if part)


def _map_type(type_name: str) -> str:
    normalized = type_name.upper()
    if normalized in {"STRING", "TIMESTAMP", "DATE", "BOOLEAN", "BIGINT", "DOUBLE"}:
        return normalized
    raise ValueError(f"Unsupported evidence column type for AWS Iceberg: {type_name}")


def _quote_identifier(value: str | None) -> str:
    if value is None:
        raise ValueError("identifier is required")
    text = str(value).strip()
    if not text:
        raise ValueError("identifier must not be empty")
    return f"`{text.replace('`', '``')}`"
