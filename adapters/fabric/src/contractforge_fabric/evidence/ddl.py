"""Fabric Lakehouse Delta DDL for ContractForge evidence tables."""

from __future__ import annotations

from contractforge_core.evidence import EVIDENCE_TABLES, EVIDENCE_TABLE_SCHEMAS
from contractforge_fabric.sql import delta_schema, quote_identifier, quote_table_name, schema_statements
from contractforge_fabric.state import render_create_state_tables_sql, state_table_names

_PARTITION_COLUMNS = {
    "runs": "run_date",
    "errors": "error_date",
    "deployments": "deployment_date",
}


def evidence_table_names(schema: str = "contractforge") -> dict[str, str]:
    return {name: f"{schema}.{table}" for name, table in EVIDENCE_TABLES.items()}


def render_create_evidence_tables_sql(*, schema: str = "contractforge", create_schema: bool = True) -> str:
    statements = schema_statements(schema, create_schema=create_schema)
    for name, table in evidence_table_names(schema).items():
        partition = _PARTITION_COLUMNS.get(name)
        partition_sql = f"PARTITIONED BY ({quote_identifier(partition)})" if partition else ""
        statements.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {quote_table_name(table)} (",
                    f"  {delta_schema(EVIDENCE_TABLE_SCHEMAS[name])}",
                    ")",
                    f"USING DELTA{(' ' + partition_sql) if partition_sql else ''};",
                ]
            )
        )
    return "\n\n".join(statements) + "\n"


def render_evidence_table_notes(*, lakehouse: str | None = None, schema: str = "contractforge") -> str:
    target = ".".join(part for part in (lakehouse, schema) if part)
    lines = [
        "-- Fabric evidence table mapping.",
        "-- These tables preserve the core ContractForge evidence/control table schema.",
        f"-- Lakehouse/schema target: {target or schema}",
        "",
    ]
    for name, table in evidence_table_names(schema).items():
        lines.append(f"-- {name}: {table}")
    for name, table in state_table_names(schema).items():
        lines.append(f"-- {name}: {table}")
    return "\n".join(lines) + "\n"


__all__ = [
    "evidence_table_names",
    "render_create_evidence_tables_sql",
    "render_create_state_tables_sql",
    "render_evidence_table_notes",
    "state_table_names",
]
