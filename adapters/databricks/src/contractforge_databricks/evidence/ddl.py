"""Databricks Delta DDL for ContractForge evidence tables."""

from __future__ import annotations

from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.evidence.schemas import EVIDENCE_TABLE_COLUMNS, EVIDENCE_TABLE_SCHEMAS
from contractforge_databricks.sql import quote_table_name

_PARTITION_COLUMNS = {
    "runs": "run_date",
    "errors": "error_date",
    "deployments": "deployment_date",
}


def render_create_evidence_tables_sql(*, catalog: str = "main", schema: str = "ops") -> str:
    table_names = evidence_table_names(catalog, schema)
    statements = [f"CREATE SCHEMA IF NOT EXISTS {quote_table_name(f'{catalog}.{schema}')};"]
    for name, table in table_names.items():
        columns = EVIDENCE_TABLE_SCHEMAS[name]
        partition = _PARTITION_COLUMNS.get(name)
        partition_sql = f"PARTITIONED BY ({partition})" if partition else ""
        statements.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {quote_table_name(table)} (",
                    f"  {columns}",
                    ")",
                    f"USING DELTA{(' ' + partition_sql) if partition_sql else ''};",
                ]
            )
        )
    return "\n\n".join(statements) + "\n"


__all__ = ["EVIDENCE_TABLE_COLUMNS", "EVIDENCE_TABLE_SCHEMAS", "render_create_evidence_tables_sql"]
