"""OpenLineage event rendering for GCP BigQuery evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import evidence_dataset, table_prefix, target_dataset, target_project, target_table_id
from contractforge_gcp.runtime import BigQueryJobEvidence

SchemaField = tuple[str, str]


def openlineage_namespace(
    contract: SemanticContract,
    *,
    environment: GCPEnvironment | None = None,
    namespace: str | None = None,
) -> str:
    if namespace:
        return namespace
    env = environment or GCPEnvironment()
    project = target_project(contract, env) or env.project_id or "unknown-project"
    return f"bigquery://{project}"


def source_name(contract: SemanticContract, *, environment: GCPEnvironment | None = None) -> str:
    source = contract.source.raw or {}
    source_type = str(source.get("type") or source.get("connector") or contract.source.kind or "").strip()
    if source_type in {"table", "view", "iceberg_table"}:
        return str(source.get("table") or source.get("table_ref") or source.get("ref") or contract.source.location)
    if source_type == "sql":
        return str(source.get("name") or source.get("query_name") or "inline_sql")
    if source.get("path"):
        return str(source["path"])
    env = environment or GCPEnvironment()
    return f"{target_project(contract, env) or env.project_id or 'unknown-project'}.{target_dataset(contract, env)}._staging_{contract.target.name}"


def build_openlineage_event(
    contract: SemanticContract,
    *,
    run_id: str,
    source_name: str,
    status: str,
    started_at_utc: datetime,
    finished_at_utc: datetime,
    rows_read: int = 0,
    rows_written: int = 0,
    input_schema: tuple[SchemaField, ...] = (),
    output_schema: tuple[SchemaField, ...] = (),
    operation_metrics: dict[str, Any] | None = None,
    environment: GCPEnvironment | None = None,
    namespace: str | None = None,
    producer: str = "contractforge-gcp",
    parent_run_id: str | None = None,
    source_code_url: str | None = None,
) -> dict[str, Any]:
    env = environment or GCPEnvironment()
    lineage_namespace = openlineage_namespace(contract, environment=env, namespace=namespace)
    target = target_table_id(contract, env)
    event = {
        "eventType": "COMPLETE" if status == "SUCCESS" else "FAIL",
        "eventTime": finished_at_utc.isoformat(),
        "producer": producer,
        "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
        "run": {
            "runId": run_id,
            "facets": _clean_none(
                {
                    "parent": _parent_facet(parent_run_id, lineage_namespace, contract, producer, source_code_url),
                    "processing_engine": {
                        "_producer": producer,
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ProcessingEngineRunFacet.json",
                        "name": "bigquery",
                        "version": None,
                    },
                }
            ),
        },
        "job": {
            "namespace": lineage_namespace,
            "name": f"{contract.target.layer}.{contract.target.name}.{contract.write.mode}",
            "facets": _clean_none({"sourceCodeLocation": _source_code_facet(source_code_url, producer)}),
        },
        "inputs": [_dataset(lineage_namespace, source_name, input_schema, producer)],
        "outputs": [_output_dataset(lineage_namespace, target, output_schema, rows_written, producer)],
        "facets": {
            "contractforge": {
                "_producer": producer,
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/RunFacet.json",
                "mode": contract.write.mode,
                "layer": contract.target.layer,
                "rowsRead": rows_read,
                "rowsWritten": rows_written,
                "operationMetrics": redact_value(operation_metrics or {}),
                "startedAt": started_at_utc.isoformat(),
                "finishedAt": finished_at_utc.isoformat(),
            }
        },
    }
    return redact_value(_clean_none(event))


def render_openlineage_insert_sql(
    contract: SemanticContract,
    *,
    environment: GCPEnvironment,
    job: BigQueryJobEvidence,
    source_name: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    started_at_utc: datetime | None = None,
    finished_at_utc: datetime | None = None,
    **kwargs: Any,
) -> str:
    run_id = run_id or job.job_id or "untracked_bigquery_job"
    finished = finished_at_utc or _datetime_from_ms(job.finished_at_ms) or datetime.now(timezone.utc)
    started = started_at_utc or _datetime_from_ms(job.started_at_ms) or finished
    event = build_openlineage_event(
        contract,
        run_id=run_id,
        source_name=source_name or globals()["source_name"](contract, environment=environment),
        status=status or ("SUCCESS" if job.ok else "FAILED"),
        started_at_utc=started,
        finished_at_utc=finished,
        rows_read=_rows_read(job),
        rows_written=_rows_written(job),
        operation_metrics=_job_metrics(job),
        environment=environment,
        **kwargs,
    )
    table = f"`{table_prefix(environment.project_id, evidence_dataset(contract, environment))}.contractforge_lineage_evidence`"
    columns = {
        "run_id": run_id,
        "target_table": target_table_id(contract, environment),
        "source_name": source_name or globals()["source_name"](contract, environment=environment),
        "event_json": json.dumps(event, separators=(",", ":"), sort_keys=True),
        "event_time": f"TIMESTAMP '{finished.isoformat()}'",
        "adapter": "gcp_bigquery",
    }
    return _insert(table, columns)


def _dataset(namespace: str, name: str, fields: tuple[SchemaField, ...], producer: str) -> dict[str, Any]:
    return {
        "namespace": namespace,
        "name": name,
        "facets": {
            "schema": {
                "_producer": producer,
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json",
                "fields": [{"name": field_name, "type": dtype} for field_name, dtype in fields],
            }
        },
    }


def _output_dataset(namespace: str, name: str, fields: tuple[SchemaField, ...], row_count: int, producer: str) -> dict[str, Any]:
    dataset = _dataset(namespace, name, fields, producer)
    dataset["facets"]["dataQualityMetrics"] = {
        "_producer": producer,
        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsOutputDatasetFacet.json",
        "rowCount": row_count,
    }
    return dataset


def _parent_facet(
    parent_run_id: str | None,
    namespace: str,
    contract: SemanticContract,
    producer: str,
    source_code_url: str | None,
) -> dict[str, Any] | None:
    if not parent_run_id:
        return None
    return {
        "_producer": producer,
        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ParentRunFacet.json",
        "job": {"namespace": namespace, "name": source_code_url or contract.target.name},
        "run": {"runId": parent_run_id},
    }


def _source_code_facet(source_code_url: str | None, producer: str) -> dict[str, Any] | None:
    if not source_code_url:
        return None
    return {
        "_producer": producer,
        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SourceCodeLocationJobFacet.json",
        "type": "bigquery",
        "url": source_code_url,
    }


def _job_metrics(job: BigQueryJobEvidence) -> dict[str, Any]:
    return {
        "jobId": job.job_id,
        "jobType": job.job_type,
        "statementType": job.statement_type,
        "totalBytesProcessed": job.total_bytes_processed,
        "totalBytesBilled": job.total_bytes_billed,
        "totalSlotMs": job.total_slot_ms,
        "insertedRows": job.inserted_rows,
        "updatedRows": job.updated_rows,
        "deletedRows": job.deleted_rows,
        "outputRows": job.output_rows,
    }


def _rows_read(job: BigQueryJobEvidence) -> int:
    return int(job.output_rows or 0)


def _rows_written(job: BigQueryJobEvidence) -> int:
    dml_rows = sum(value or 0 for value in (job.inserted_rows, job.updated_rows, job.deleted_rows))
    return int(dml_rows or job.output_rows or 0)


def _datetime_from_ms(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def _insert(table: str, columns: dict[str, Any]) -> str:
    names = tuple(columns)
    column_sql = ", ".join(_identifier(name) for name in names)
    values = ", ".join(_literal(columns[name]) for name in names)
    return f"INSERT INTO {table} ({column_sql}) VALUES ({values});"


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and value.startswith("TIMESTAMP '"):
        return value
    return _string(str(value))


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


def _clean_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_clean_none(item) for item in value if item is not None]
    return value
