"""Render AWS Iceberg evidence INSERT statements."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from contractforge_core.evidence import CostEvidenceRecord, LineageEvidenceRecord, RunEvidenceRecord
from contractforge_core.deployment import DEPLOYMENT_LEDGER_COLUMNS
from contractforge_core.security import redact_value
from contractforge_aws.evidence.ddl import evidence_table_names
from contractforge_aws.evidence.glue import GlueJobRunEvidence


def render_run_insert_sql(record: RunEvidenceRecord, *, database: str = "contractforge_ops") -> str:
    table = evidence_table_names(database)["runs"]
    metrics = record.metrics or {}
    columns = {
        "run_id": record.run_id,
        "target_table": record.target_table,
        "mode": record.mode,
        "status": record.status,
        "started_at_utc": record.started_at_utc,
        "finished_at_utc": record.finished_at_utc,
        "duration_seconds": metrics.get("duration_seconds"),
        "metrics_source": metrics.get("metrics_source"),
        "runtime_type": metrics.get("runtime_type"),
        "master_job_id": metrics.get("master_job_id"),
        "master_run_id": metrics.get("master_run_id"),
        "error_message": metrics.get("error_message"),
        "operation_metrics_json": metrics.get("operation_metrics_json") or {},
        "metrics_json": metrics,
    }
    return _insert(table, columns)


def render_cost_insert_sql(record: CostEvidenceRecord, *, database: str = "contractforge_ops") -> str:
    table = evidence_table_names(database)["cost"]
    columns = {
        "run_id": record.run_id,
        "target_table": record.target_table,
        "signal_name": record.signal_name,
        "signal_value": record.signal_value,
        "payload_json": record.payload,
        "captured_at_utc": record.captured_at_utc,
    }
    return _insert(table, columns)


def render_lineage_insert_sql(record: LineageEvidenceRecord, *, database: str = "contractforge_ops") -> str:
    table = evidence_table_names(database)["lineage"]
    columns = {
        "run_id": record.run_id,
        "event_time_utc": record.event_time_utc,
        "event_type": record.event.get("eventType"),
        "target_table": record.target_table,
        "source_table": record.source_name,
        "source_name": record.source_name,
        "namespace": record.event.get("job", {}).get("namespace"),
        "producer": record.event.get("producer"),
        "event_json": record.event,
    }
    return _insert(table, columns)


def render_glue_run_evidence_sql(evidence: GlueJobRunEvidence, *, database: str = "contractforge_ops") -> str:
    statements = [render_run_insert_sql(evidence.run, database=database)]
    if evidence.cost is not None:
        statements.append(render_cost_insert_sql(evidence.cost, database=database))
    return "\n\n".join(statements) + "\n"


def render_deployment_ledger_insert_sql(record: dict[str, Any], *, database: str = "contractforge_ops") -> str:
    table = evidence_table_names(database)["deployments"]
    return _insert(table, {column: record.get(column) for column in DEPLOYMENT_LEDGER_COLUMNS})


def _insert(table: str, columns: dict[str, Any]) -> str:
    filtered = {key: value for key, value in columns.items() if value is not None}
    names = ", ".join(_quote_identifier(name) for name in filtered)
    values = ", ".join(_literal(value) for value in filtered.values())
    return f"INSERT INTO {table} ({names}) VALUES ({values});"


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP {_string(value.strftime('%Y-%m-%d %H:%M:%S'))}"
    if isinstance(value, date):
        return f"DATE {_string(value.isoformat())}"
    if isinstance(value, dict):
        return _string(json.dumps(redact_value(value), sort_keys=True, separators=(",", ":")))
    return _string(redact_value(str(value)))


def _string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_identifier(value: str) -> str:
    return f"`{str(value).replace('`', '``')}`"
