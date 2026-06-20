"""Render annotation audit SQL for Databricks evidence tables."""

from __future__ import annotations

from datetime import datetime

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.annotations.sql import annotation_steps
from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_table_name, sql_string


def render_annotations_audit_insert_sql(
    contract: SemanticContract,
    *,
    run_id: str = "${run_id}",
    status: str = "PLANNED",
    captured_at_utc: datetime | None = None,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    steps = annotation_steps(contract)
    if not steps:
        return "-- No annotations intent declared.\n"
    table = evidence_table_names(catalog, schema)["annotations"]
    captured_at_utc = captured_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    statements = [
        _audit_insert(table, run_id, target_full_name(contract), step, status, captured_at_utc)
        for step in steps
    ]
    return ";\n".join(statements) + ";\n"


def _audit_insert(table: str, run_id: str, target: str, step: dict[str, object], status: str, captured_at_utc: datetime) -> str:
    columns = "run_id, target_table, annotation_scope, annotation_type, column_name, key, value, status, applied_sql, annotation_ts_utc"
    values = [
        sql_string(run_id),
        sql_string(target),
        sql_string(step.get("annotation_scope")),
        sql_string(step.get("annotation_type")),
        sql_string(step.get("column_name")),
        sql_string(step.get("key")),
        sql_string(step.get("value")),
        sql_string(status),
        sql_string(step.get("sql")),
        f"TIMESTAMP {sql_string(captured_at_utc.strftime('%Y-%m-%d %H:%M:%S'))}",
    ]
    return f"INSERT INTO {quote_table_name(table)} ({columns}) VALUES ({', '.join(values)})"
