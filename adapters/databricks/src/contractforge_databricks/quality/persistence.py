"""Databricks SQL rendering for quality and quarantine persistence."""

from __future__ import annotations

import json
from datetime import datetime

from contractforge_core.quality import QualityRuleResult
from contractforge_databricks.evidence import QuarantineEvidenceRecord
from contractforge_databricks.evidence.sql import render_quarantine_insert_sql
from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.sql import quote_table_name, sql_int, sql_string


def render_quality_result_insert_sql(
    *,
    run_id: str,
    target_table: str,
    result: QualityRuleResult,
    checked_at_utc: datetime,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    table = evidence_table_names(catalog, schema)["quality"]
    checked_at = checked_at_utc.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"INSERT INTO {quote_table_name(table)} "
        "(run_id, target_table, rule_name, status, severity, failed_count, observed_value, "
        "checked_at_utc, message, details_json) VALUES "
        f"({sql_string(run_id)}, {sql_string(target_table)}, {sql_string(result.rule_name)}, "
        f"{sql_string(result.status)}, {sql_string(result.severity)}, {sql_int(result.failed_count)}, "
        f"{_json(result.as_dict())}, TIMESTAMP {sql_string(checked_at)}, "
        f"{sql_string(result.message)}, {_json(result.details or {})})"
    )


def render_quality_results_insert_sql(
    *,
    run_id: str,
    target_table: str,
    results: tuple[QualityRuleResult, ...],
    checked_at_utc: datetime,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    statements = [
        render_quality_result_insert_sql(
            run_id=run_id,
            target_table=target_table,
            result=result,
            checked_at_utc=checked_at_utc,
            catalog=catalog,
            schema=schema,
        )
        for result in results
    ]
    return ";\n".join(statements) + (";\n" if statements else "-- No quality results to persist.\n")


def render_quarantine_reference_insert_sql(
    *,
    run_id: str,
    target_table: str,
    record_ref: str,
    reason: str,
    quarantined_at_utc: datetime,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    record = QuarantineEvidenceRecord(
        run_id=run_id,
        target_table=target_table,
        record_ref=record_ref,
        reason=reason,
        quarantined_at_utc=quarantined_at_utc,
    )
    return render_quarantine_insert_sql(record, catalog=catalog, schema=schema)


def _json(value: object) -> str:
    return sql_string(json.dumps(value, sort_keys=True, separators=(",", ":")))
