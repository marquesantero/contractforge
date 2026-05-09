"""Captura de plano (explain) e emissão de eventos OpenLineage."""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from datetime import datetime
from typing import Any, Dict, List, Optional

from pyspark.sql import DataFrame

from .plan import IngestionPlan
from ._spark import spark
from ._sql import qt, safe_truncate, sql_lit, to_json


def capture_explain(df: DataFrame, mode: str = "formatted") -> str:
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            df.explain(mode=mode)
        return buffer.getvalue()
    except TypeError:
        with redirect_stdout(buffer):
            df.explain(True)
        return buffer.getvalue()


def write_explain_plan(
    tables: Dict[str, str],
    run_id: str,
    target: str,
    source_name: str,
    mode: str,
    explain_format: str,
    plan_text: str,
) -> None:
    if not plan_text:
        return
    spark.sql(f"""
        INSERT INTO {qt(tables['explain'])} (
            run_id, target_table, source_table, mode, explain_format, plan_text, captured_at_utc
        ) VALUES (
            {sql_lit(run_id)}, {sql_lit(target)}, {sql_lit(source_name)}, {sql_lit(mode)},
            {sql_lit(explain_format)}, {sql_lit(safe_truncate(plan_text, 100000))}, current_timestamp()
        )
    """)


def openlineage_namespace(plan: IngestionPlan) -> str:
    if plan.openlineage_namespace:
        return plan.openlineage_namespace
    return f"databricks://{plan.catalog}"


def _schema_fields(df: Optional[DataFrame]) -> List[Dict[str, str]]:
    if df is None:
        return []
    return [{"name": field.name, "type": field.dataType.simpleString()} for field in df.schema.fields]


def _clean_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_clean_none(v) for v in value if v is not None]
    return value


def build_openlineage_event(
    plan: IngestionPlan,
    run_id: str,
    target: str,
    source_name: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    input_df: Optional[DataFrame],
    output_df: Optional[DataFrame],
    rows_read: int,
    rows_written: int,
    delta_version_before: Optional[int],
    delta_version_after: Optional[int],
    operation_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    namespace = openlineage_namespace(plan)
    event_type = "COMPLETE" if status == "SUCCESS" else "FAIL"
    parent_facet = (
        {
            "_producer": plan.openlineage_producer,
            "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ParentRunFacet.json",
            "job": {"namespace": namespace, "name": plan.notebook_name},
            "run": {"runId": plan.parent_run_id or run_id},
        }
        if plan.parent_run_id
        else None
    )
    return {
        "eventType": event_type,
        "eventTime": finished_at.isoformat(),
        "producer": plan.openlineage_producer,
        "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
        "run": {
            "runId": run_id,
            "facets": {
                "parent": parent_facet,
                "processing_engine": {
                    "_producer": plan.openlineage_producer,
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ProcessingEngineRunFacet.json",
                    "version": spark.version,
                    "name": "spark",
                },
            },
        },
        "job": {
            "namespace": namespace,
            "name": f"{plan.layer}.{plan.target_table}.{plan.mode}",
            "facets": {
                "sourceCodeLocation": {
                    "_producer": plan.openlineage_producer,
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SourceCodeLocationJobFacet.json",
                    "type": "notebook",
                    "url": plan.notebook_name,
                }
            },
        },
        "inputs": [
            {
                "namespace": namespace,
                "name": source_name,
                "facets": {
                    "schema": {
                        "_producer": plan.openlineage_producer,
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json",
                        "fields": _schema_fields(input_df),
                    }
                },
            }
        ],
        "outputs": [
            {
                "namespace": namespace,
                "name": target,
                "facets": {
                    "schema": {
                        "_producer": plan.openlineage_producer,
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json",
                        "fields": _schema_fields(output_df),
                    },
                    "dataQualityMetrics": {
                        "_producer": plan.openlineage_producer,
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsOutputDatasetFacet.json",
                        "rowCount": rows_written,
                    },
                },
            }
        ],
        "facets": {
            "lakehouse_ingestion": {
                "_producer": plan.openlineage_producer,
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/RunFacet.json",
                "mode": plan.mode,
                "layer": plan.layer,
                "rowsRead": rows_read,
                "rowsWritten": rows_written,
                "deltaVersionBefore": delta_version_before,
                "deltaVersionAfter": delta_version_after,
                "operationMetrics": operation_metrics,
                "startedAt": started_at.isoformat(),
                "finishedAt": finished_at.isoformat(),
            }
        },
    }


def write_openlineage_event(
    tables: Dict[str, str],
    plan: IngestionPlan,
    run_id: str,
    target: str,
    source_name: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    input_df: Optional[DataFrame],
    output_df: Optional[DataFrame],
    rows_read: int,
    rows_written: int,
    delta_version_before: Optional[int],
    delta_version_after: Optional[int],
    operation_metrics: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not plan.openlineage_enabled:
        return None
    event = _clean_none(
        build_openlineage_event(
            plan,
            run_id,
            target,
            source_name,
            status,
            started_at,
            finished_at,
            input_df,
            output_df,
            rows_read,
            rows_written,
            delta_version_before,
            delta_version_after,
            operation_metrics,
        )
    )
    event_type = event.get("eventType", status)
    spark.sql(f"""
        INSERT INTO {qt(tables['lineage'])} (
            run_id, event_time_utc, event_type, target_table, source_table, namespace, producer, event_json
        ) VALUES (
            {sql_lit(run_id)}, {sql_lit(finished_at.strftime('%Y-%m-%d %H:%M:%S'))},
            {sql_lit(event_type)}, {sql_lit(target)}, {sql_lit(source_name)},
            {sql_lit(openlineage_namespace(plan))}, {sql_lit(plan.openlineage_producer)},
            {sql_lit(to_json(event))}
        )
    """)
    return event
