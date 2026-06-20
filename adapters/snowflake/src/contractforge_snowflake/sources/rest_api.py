"""Snowflake REST API source materialization."""

from __future__ import annotations

import json
import re
from typing import Any

from contractforge_core.connectors.api.rest import read_rest_api_records
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.sources.models import SnowflakeSourcePlan
from contractforge_snowflake.sql import sql_string

_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_]+")


def materialize_rest_api_source(
    *,
    contract: SemanticContract,
    session: Any,
    run_id: str | None,
) -> SnowflakeSourcePlan:
    """Fetch a bounded REST source and materialize it as a temporary table."""

    source = contract.source.raw or {}
    records = read_rest_api_records(source)
    columns = _columns(records, source=source)
    table_name = quote_identifier(_temporary_table_name(contract, run_id=run_id))
    commands = (
        _create_table_sql(table_name, columns),
        *_insert_sql(table_name, columns, records),
    )
    return SnowflakeSourcePlan(
        sql=f"SELECT * FROM {table_name}",
        metadata={
            "type": "rest_api",
            "url": _source_url(source),
            "method": _source_method(source),
            "response_mode": _response_mode(source),
            "records_materialized": len(records),
        },
        commands=commands,
    )


def _temporary_table_name(contract: SemanticContract, *, run_id: str | None) -> str:
    target = "_".join((*contract.target.namespace.split("."), contract.target.name))
    suffix = _IDENTIFIER_RE.sub("_", str(run_id or "local")).strip("_")[:32]
    base = _IDENTIFIER_RE.sub("_", target).strip("_").upper() or "SOURCE"
    return f"CF_REST_{base}_{suffix}".strip("_")[:240]


def _columns(records: list[dict[str, Any]], *, source: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    if not records:
        response = source.get("response") if isinstance(source.get("response"), dict) else {}
        if str(response.get("mode") or "").lower() == "raw":
            return ((str(response.get("raw_column") or "raw_response"), "VARCHAR"), ("response_page_number", "NUMBER"))
        return (("payload", "VARIANT"),)
    names: list[str] = []
    for record in records:
        for name in record:
            if name not in names:
                names.append(str(name))
    return tuple((name, _snowflake_type([record.get(name) for record in records])) for name in names)


def _snowflake_type(values: list[Any]) -> str:
    concrete = [value for value in values if value is not None]
    if not concrete:
        return "VARCHAR"
    if all(isinstance(value, bool) for value in concrete):
        return "BOOLEAN"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in concrete):
        return "NUMBER"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in concrete):
        return "FLOAT"
    if any(isinstance(value, (dict, list, tuple)) for value in concrete):
        return "VARIANT"
    return "VARCHAR"


def _create_table_sql(table_name: str, columns: tuple[tuple[str, str], ...]) -> str:
    column_sql = ", ".join(f"{quote_identifier(name)} {column_type}" for name, column_type in columns)
    return f"CREATE OR REPLACE TEMPORARY TABLE {table_name} ({column_sql})"


def _insert_sql(table_name: str, columns: tuple[tuple[str, str], ...], records: list[dict[str, Any]]) -> tuple[str, ...]:
    if not records:
        return ()
    column_names = ", ".join(quote_identifier(name) for name, _type in columns)
    rows = []
    for record in records:
        values = ", ".join(_sql_value(record.get(name), column_type) for name, column_type in columns)
        rows.append(f"({values})")
    return (f"INSERT INTO {table_name} ({column_names}) VALUES\n" + ",\n".join(rows),)


def _sql_value(value: Any, column_type: str) -> str:
    if value is None:
        return "NULL"
    if column_type == "BOOLEAN":
        return "TRUE" if bool(value) else "FALSE"
    if column_type in {"NUMBER", "FLOAT"}:
        return str(value)
    if column_type == "VARIANT":
        return "PARSE_JSON(" + sql_string(json.dumps(value, sort_keys=True, default=str)) + ")"
    return sql_string(value)


def _source_url(source: dict[str, Any]) -> str | None:
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    value = source.get("url") or request.get("url")
    return str(value) if value not in (None, "") else None


def _source_method(source: dict[str, Any]) -> str:
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    return str(request.get("method") or "GET").upper()


def _response_mode(source: dict[str, Any]) -> str:
    response = source.get("response") if isinstance(source.get("response"), dict) else {}
    return str(response.get("mode") or "records").lower()


__all__ = ["materialize_rest_api_source"]
