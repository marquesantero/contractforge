"""Fabric deployment ledger SQL rendering."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from contractforge_core.deployment import DEPLOYMENT_LEDGER_COLUMNS
from contractforge_fabric.evidence import evidence_table_names, render_create_evidence_tables_sql
from contractforge_fabric.sql import quote_identifier, quote_table_name, sql_int, sql_string


def render_deployment_ledger_ddl_sql(*, schema: str = "contractforge", create_schema: bool = True) -> str:
    return render_create_evidence_tables_sql(schema=schema, create_schema=create_schema)


def render_deployment_ledger_insert_sql(record: Mapping[str, Any], *, schema: str = "contractforge") -> str:
    table = evidence_table_names(schema)["deployments"]
    columns = [column for column in DEPLOYMENT_LEDGER_COLUMNS if record.get(column) is not None]
    names = ", ".join(quote_identifier(column) for column in columns)
    values = ", ".join(_literal(record[column]) for column in columns)
    return f"INSERT INTO {quote_table_name(table)} ({names}) VALUES ({values});"


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int) and not isinstance(value, bool):
        return sql_int(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP {sql_string(value.strftime('%Y-%m-%d %H:%M:%S'))}"
    if isinstance(value, date):
        return f"DATE {sql_string(value.isoformat())}"
    return sql_string(value)


__all__ = ["render_deployment_ledger_ddl_sql", "render_deployment_ledger_insert_sql"]
