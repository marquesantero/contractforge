"""Render BigQuery evidence INSERT statements."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from contractforge_core.deployment import DEPLOYMENT_LEDGER_COLUMNS
from contractforge_core.evidence import EVIDENCE_TABLES
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import evidence_dataset, table_prefix, target_table_id
from contractforge_gcp.runtime import BigQueryJobEvidence


def render_run_evidence_insert_sql(
    *,
    environment: GCPEnvironment,
    contract: SemanticContract,
    job: BigQueryJobEvidence,
) -> str:
    table = _qualified_table(environment, contract, "contractforge_run_evidence")
    columns = {
        "run_id": _run_id(job),
        "contract_name": contract.target.name,
        "target_table": target_table_id(contract, environment),
        "adapter": "gcp_bigquery",
        "status": _job_status(job),
        "started_at": _timestamp_literal(job.started_at_ms),
        "finished_at": _timestamp_literal(job.finished_at_ms),
        "total_bytes_processed": job.total_bytes_processed,
        "total_bytes_billed": job.total_bytes_billed,
        "total_slot_ms": job.total_slot_ms,
        "job_id": job.job_id,
        "statement_type": job.statement_type or job.job_type,
        "inserted_rows": job.inserted_rows,
        "updated_rows": job.updated_rows,
        "deleted_rows": job.deleted_rows,
        "error_message": job.error_message,
    }
    return _insert(table, columns)


def render_quality_evidence_insert_sql(
    *,
    environment: GCPEnvironment,
    contract: SemanticContract,
    job: BigQueryJobEvidence,
) -> str:
    table = _qualified_table(environment, contract, "contractforge_quality_evidence")
    rows = _quality_rows(contract, job)
    return _insert_many(table, rows)


def render_schema_evidence_insert_sql(
    *,
    environment: GCPEnvironment,
    contract: SemanticContract,
    job: BigQueryJobEvidence,
) -> str:
    table = _qualified_table(environment, contract, "contractforge_schema_evidence")
    schema_changes = _schema_policy_payload(job)
    return _insert(
        table,
        {
            "run_id": _run_id(job),
            "contract_name": contract.target.name,
            "target_table": target_table_id(contract, environment),
            "schema_policy": contract.write.schema_policy,
            "status": _job_status(job),
            "added_columns": _change_columns(schema_changes, "added_columns"),
            "removed_columns": _change_columns(schema_changes, "removed_columns"),
            "type_changes_json": json.dumps(schema_changes.get("type_changes", ()), sort_keys=True),
            "schema_changes_json": json.dumps(schema_changes, sort_keys=True),
            "evaluated_at": _timestamp_literal(job.finished_at_ms) or "CURRENT_TIMESTAMP()",
            "error_message": job.error_message,
        },
    )


def render_deployment_ledger_insert_sql(
    record: dict[str, Any],
    *,
    environment: GCPEnvironment,
    dataset: str | None = None,
) -> str:
    table = f"`{table_prefix(environment.project_id, dataset or environment.evidence_dataset or 'contractforge_ops')}.{EVIDENCE_TABLES['deployments']}`"
    return _insert(table, {column: record.get(column) for column in DEPLOYMENT_LEDGER_COLUMNS})


def _quality_rows(contract: SemanticContract, job: BigQueryJobEvidence) -> list[dict[str, Any]]:
    result_rows = job.result_rows or [{}]
    quality_rules = contract.quality or ()
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(result_rows):
        rule = quality_rules[index] if index < len(quality_rules) else None
        failed_rows = _failed_rows(row)
        rows.append(
            {
                "run_id": _run_id(job),
                "contract_name": contract.target.name,
                "rule_name": rule.name if rule else str(row.get("rule_name") or f"quality_{index + 1}"),
                "rule_type": rule.rule if rule else str(row.get("rule_type") or "unknown"),
                "status": _quality_status(job, failed_rows),
                "failed_rows": failed_rows,
                "evaluated_at": _timestamp_literal(job.finished_at_ms) or "CURRENT_TIMESTAMP()",
            }
        )
    return rows


def _schema_policy_payload(job: BigQueryJobEvidence) -> dict[str, Any]:
    raw = job.raw if isinstance(job.raw, dict) else {}
    payload = raw.get("schema_policy") if isinstance(raw.get("schema_policy"), dict) else {}
    changes = payload.get("schema_changes") if isinstance(payload.get("schema_changes"), dict) else {}
    return dict(changes)


def _change_columns(schema_changes: dict[str, Any], key: str) -> list[str]:
    values = schema_changes.get(key)
    if not isinstance(values, (list, tuple)):
        return []
    return [str(item["column"]) for item in values if isinstance(item, dict) and item.get("column")]


def _qualified_table(environment: GCPEnvironment, contract: SemanticContract, name: str) -> str:
    dataset = evidence_dataset(contract, environment)
    return f"`{table_prefix(environment.project_id, dataset)}.{name}`"


def _insert(table: str, columns: dict[str, Any]) -> str:
    return _insert_many(table, [columns])


def _insert_many(table: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        raise ValueError("BigQuery evidence insert requires at least one row.")
    names = tuple(rows[0])
    columns = ", ".join(_identifier(name) for name in names)
    values = ",\n  ".join("(" + ", ".join(_literal(row.get(name)) for name in names) + ")" for row in rows)
    return f"INSERT INTO {table} ({columns}) VALUES\n  {values};"


def _quality_status(job: BigQueryJobEvidence, failed_rows: int | None) -> str:
    if not job.ok:
        return "FAILED"
    if failed_rows is None:
        return "UNKNOWN"
    return "PASSED" if failed_rows == 0 else "FAILED"


def _job_status(job: BigQueryJobEvidence) -> str:
    return "SUCCEEDED" if job.ok else "FAILED"


def _run_id(job: BigQueryJobEvidence) -> str:
    return job.job_id or "untracked_bigquery_job"


def _failed_rows(row: dict[str, Any]) -> int | None:
    value = row.get("failed_rows", row.get("failed_groups"))
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _timestamp_literal(value: int | None) -> str | None:
    if value is None:
        return None
    return f"TIMESTAMP_MILLIS({value})"


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, list):
        return _array_literal(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP {_string(value.strftime('%Y-%m-%d %H:%M:%S'))}"
    if isinstance(value, date):
        return f"DATE {_string(value.isoformat())}"
    if isinstance(value, str) and (value.startswith("TIMESTAMP_MILLIS(") or value == "CURRENT_TIMESTAMP()"):
        return value
    return _string(str(value))


def _array_literal(values: list[str]) -> str:
    return "[" + ", ".join(_string(value) for value in values) + "]"


def _string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
        .replace("'", "\\'")
    )
    return "'" + escaped + "'"


def _identifier(value: str) -> str:
    return f"`{value.replace('`', '')}`"
