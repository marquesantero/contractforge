"""AWS project-level cost evidence reconciliation helpers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from contractforge_core.evidence import CostEvidenceRecord
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws.cli.project_support import project_evidence_database
from contractforge_aws.rendering.names import iceberg_table_name
from contractforge_aws.runtime import AthenaSqlRunner, reconcile_aws_glue_job_run_evidence


def record_project_step_cost_evidence(
    environment: dict | None,
    contract: dict,
    *,
    job_name: str,
    run_id: str,
    athena_output_location: str,
    athena_workgroup: str | None,
    poll_interval_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    database = project_evidence_database(environment)
    semantic = semantic_contract_from_mapping(contract)
    target_table = iceberg_table_name(semantic)
    evidence = reconcile_aws_glue_job_run_evidence(
        job_name=job_name,
        run_id=run_id,
        target_table=target_table,
        mode=semantic.write.mode,
    )
    if evidence.cost is None:
        return {
            "database": database,
            "run_id": run_id,
            "target_table": target_table,
            "status": "NO_COST_SIGNAL",
        }
    cost = _contractforge_cost_record(evidence.cost, job_name=job_name, glue_run_id=run_id)
    runner = AthenaSqlRunner(
        database=database,
        output_location=athena_output_location,
        workgroup=athena_workgroup,
        wait=True,
        poll_interval_seconds=poll_interval_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    existing = _existing_cost_rows(runner, database=database, run_id=cost.run_id, target_table=target_table)
    if existing > 0:
        return {
            "database": database,
            "run_id": cost.run_id,
            "target_table": target_table,
            "signal_name": cost.signal_name,
            "signal_value": cost.signal_value,
            "status": "ALREADY_RECORDED",
        }
    result = runner.sql(_athena_cost_insert_sql(cost, database=database))
    return {
        "database": database,
        "run_id": cost.run_id,
        "target_table": target_table,
        "signal_name": cost.signal_name,
        "signal_value": cost.signal_value,
        "status": "RECORDED",
        "query_execution_id": result.query_execution_id,
    }


def _contractforge_cost_record(record: CostEvidenceRecord, *, job_name: str, glue_run_id: str) -> CostEvidenceRecord:
    payload = dict(record.payload or {})
    payload.setdefault("contractforge_run_id", f"{job_name}:{glue_run_id}")
    payload.setdefault("glue_run_id", glue_run_id)
    return CostEvidenceRecord(
        run_id=f"{job_name}:{glue_run_id}",
        target_table=record.target_table,
        signal_name=record.signal_name,
        signal_value=record.signal_value,
        payload=payload,
        captured_at_utc=record.captured_at_utc,
    )


def _existing_cost_rows(runner: AthenaSqlRunner, *, database: str, run_id: str, target_table: str) -> int:
    rows = runner.query(
        "\n".join(
            [
                "SELECT count(*) AS existing",
                f"FROM {_athena_table(database, 'ctrl_ingestion_cost')}",
                f"WHERE run_id = {_literal(run_id)}",
                f"  AND target_table = {_literal(target_table)}",
                "  AND signal_name = 'glue_dpu_seconds'",
            ]
        )
    )
    if not rows:
        return 0
    value = rows[0].get("existing")
    return int(value or 0)


def _athena_cost_insert_sql(record, *, database: str) -> str:
    columns = {
        "run_id": record.run_id,
        "target_table": record.target_table,
        "signal_name": record.signal_name,
        "signal_value": record.signal_value,
        "payload_json": record.payload,
        "captured_at_utc": record.captured_at_utc,
    }
    names = ", ".join(_quote_identifier(name) for name, value in columns.items() if value is not None)
    values = ", ".join(_literal(value) for value in columns.values() if value is not None)
    return f"INSERT INTO {_athena_table(database, 'ctrl_ingestion_cost')} ({names}) VALUES ({values})"


def _athena_table(database: str, table: str) -> str:
    return f"{_quote_identifier(database)}.{_quote_identifier(table)}"


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return "TIMESTAMP " + _literal(value.strftime("%Y-%m-%d %H:%M:%S"))
    if isinstance(value, dict):
        return _literal(json.dumps(value, sort_keys=True, separators=(",", ":")))
    return "'" + str(value).replace("'", "''") + "'"
