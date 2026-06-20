"""Databricks explain-plan diagnostic SQL."""

from __future__ import annotations

from contractforge_core.diagnostics import ExplainPlanRecord
from contractforge_databricks.security import redact_text
from contractforge_databricks.sql import quote_table_name, sql_string


def render_create_explain_table_sql(*, catalog: str = "main", schema: str = "ops") -> str:
    table = f"{catalog}.{schema}.ctrl_ingestion_explain"
    return "\n".join(
        [
            f"CREATE SCHEMA IF NOT EXISTS {quote_table_name(f'{catalog}.{schema}')};",
            "",
            f"CREATE TABLE IF NOT EXISTS {quote_table_name(table)} (",
            "  run_id STRING, target_table STRING, source_table STRING, mode STRING,",
            "  explain_format STRING, plan_text STRING, captured_at_utc TIMESTAMP",
            ")",
            "USING DELTA;",
            "",
        ]
    )


def render_explain_insert_sql(
    record: ExplainPlanRecord,
    *,
    catalog: str = "main",
    schema: str = "ops",
    truncate_at: int = 100_000,
) -> str:
    table = f"{catalog}.{schema}.ctrl_ingestion_explain"
    plan_text = redact_text(record.plan_text)[:truncate_at]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, source_table, mode, explain_format, plan_text, captured_at_utc) VALUES "
        f"({sql_string(record.run_id)}, {sql_string(record.target_table)}, {sql_string(record.source_name)}, "
        f"{sql_string(record.mode)}, {sql_string(record.explain_format)}, {sql_string(plan_text)}, current_timestamp())"
    )
