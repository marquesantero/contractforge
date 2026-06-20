"""Full ContractForge run ledger SQL rendering."""

from __future__ import annotations

import json
from typing import Any

from contractforge_databricks.evidence.helpers import cast_sql
from contractforge_databricks.evidence.schemas import EVIDENCE_TABLE_COLUMNS
from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.security import redact_text, redact_value
from contractforge_databricks.sql import quote_table_name, sql_int, sql_string

RUN_COLUMNS = tuple(column.split(" ", 1)[0] for column in EVIDENCE_TABLE_COLUMNS["runs"])
RUN_INT_COLUMNS = {
    "rows_read",
    "rows_written",
    "rows_inserted",
    "rows_updated",
    "rows_deleted",
    "rows_expired",
    "rows_quarantined",
    "ctrl_schema_version",
}
RUN_FLOAT_COLUMNS = {"duration_seconds"}
RUN_BOOL_COLUMNS = {"write_committed"}
RUN_DATE_COLUMNS = {"run_date"}
RUN_TIMESTAMP_COLUMNS = {
    "run_ts_utc",
    "started_at_utc",
    "finished_at_utc",
    "write_started_at_utc",
    "write_finished_at_utc",
}


def render_run_log_insert_sql(
    payload: dict[str, Any],
    *,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    table = evidence_table_names(catalog, schema)["runs"]
    values = [_render_run_value(column, payload.get(column)) for column in RUN_COLUMNS]
    return (
        f"INSERT INTO {quote_table_name(table)} ({', '.join(RUN_COLUMNS)}) VALUES "
        f"({', '.join(values)})"
    )


def _render_run_value(column: str, value: Any) -> str:
    if column in RUN_INT_COLUMNS:
        return sql_int(value)
    if column in RUN_FLOAT_COLUMNS:
        return "NULL" if value is None else str(float(value))
    if column in RUN_BOOL_COLUMNS:
        return "NULL" if value is None else str(bool(value)).lower()
    if column in RUN_DATE_COLUMNS:
        return cast_sql(value, "DATE")
    if column in RUN_TIMESTAMP_COLUMNS or column.endswith("_utc"):
        return cast_sql(value, "TIMESTAMP")
    if column.endswith("_json"):
        return sql_string(_json_text(value))
    if column == "error_message":
        return sql_string(redact_text(str(value))[:4000] if value is not None else None)
    return sql_string(redact_value(value))


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return redact_text(value)
    return json.dumps(redact_value(value), sort_keys=True, separators=(",", ":"))
