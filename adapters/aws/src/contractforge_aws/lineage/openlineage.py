"""OpenLineage event rendering for AWS Glue/Iceberg evidence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from contractforge_core.evidence import LineageEvidenceRecord
from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence import render_lineage_insert_sql
from contractforge_aws.rendering.names import glue_database_name, iceberg_table_name
from contractforge_aws.security import redact_value

SchemaField = tuple[str, str]


def openlineage_namespace(contract: SemanticContract, *, namespace: str | None = None) -> str:
    if namespace:
        return namespace
    return f"aws-glue://{glue_database_name(contract)}"


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
    iceberg_snapshot_after: str | None = None,
    operation_metrics: dict[str, Any] | None = None,
    namespace: str | None = None,
    producer: str = "contractforge-aws",
    parent_run_id: str | None = None,
    spark_version: str | None = None,
    source_code_url: str | None = None,
) -> dict[str, Any]:
    lineage_namespace = openlineage_namespace(contract, namespace=namespace)
    target = iceberg_table_name(contract)
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
                        "name": "spark",
                        "version": spark_version,
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
                "icebergSnapshotAfter": iceberg_snapshot_after,
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
    run_id: str,
    source_name: str,
    status: str,
    started_at_utc: datetime,
    finished_at_utc: datetime,
    database: str = "contractforge_ops",
    **kwargs: Any,
) -> str:
    event = build_openlineage_event(
        contract,
        run_id=run_id,
        source_name=source_name,
        status=status,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
        **kwargs,
    )
    record = LineageEvidenceRecord(
        run_id=run_id,
        target_table=iceberg_table_name(contract),
        source_name=source_name,
        event=json.loads(json.dumps(event, sort_keys=True)),
        event_time_utc=finished_at_utc,
    )
    return render_lineage_insert_sql(record, database=database)


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
    job_name = source_code_url or contract.target.name
    return {
        "_producer": producer,
        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ParentRunFacet.json",
        "job": {"namespace": namespace, "name": job_name},
        "run": {"runId": parent_run_id},
    }


def _source_code_facet(source_code_url: str | None, producer: str) -> dict[str, Any] | None:
    if not source_code_url:
        return None
    return {
        "_producer": producer,
        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SourceCodeLocationJobFacet.json",
        "type": "glue_job",
        "url": source_code_url,
    }


def _clean_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_clean_none(item) for item in value if item is not None]
    return value
