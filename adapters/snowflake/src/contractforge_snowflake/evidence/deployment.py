"""Snowflake deployment ledger SQL rendering."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from contractforge_core.deployment import DEPLOYMENT_LEDGER_COLUMNS
from contractforge_core.evidence import EVIDENCE_TABLES
from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.sql import sql_string


def render_deployment_ledger_insert_sql(
    record: Mapping[str, Any],
    *,
    database: str = "CONTRACTFORGE",
    schema: str = "CF_EVIDENCE",
) -> str:
    table = (
        f"{quote_identifier(database)}."
        f"{quote_identifier(schema)}."
        f"{quote_identifier(EVIDENCE_TABLES['deployments'])}"
    )
    columns = [column for column in DEPLOYMENT_LEDGER_COLUMNS if record.get(column) is not None]
    names = ", ".join(quote_identifier(column) for column in columns)
    values = ", ".join(_literal(record[column]) for column in columns)
    return f"INSERT INTO {table} ({names}) VALUES ({values});"


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, datetime):
        return f"TO_TIMESTAMP_NTZ({sql_string(value.strftime('%Y-%m-%d %H:%M:%S'))})"
    if isinstance(value, date):
        return f"TO_DATE({sql_string(value.isoformat())})"
    return sql_string(value)


__all__ = ["render_deployment_ledger_insert_sql"]
