"""Available-now stream orchestration helpers for Databricks."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from contractforge_core.runtime import PreparedInput
from contractforge_core.runtime import QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.evidence import EvidenceWriter, render_stream_child_run_metrics_sql
from contractforge_databricks.runtime.sources import resolve_source_dataframe
from contractforge_databricks.sources.interpret import interpret_incremental_files_source, is_incremental_file_source
from contractforge_databricks.runtime.streaming import (
    prefer_child_stream_metrics,
    stream_metrics_from_batches,
    stream_result_payload,
    stream_start_payload,
)

BatchIngestor = Callable[[PreparedInput, int], dict[str, Any]]


def run_available_now_stream(
    spark: Any,
    contract: SemanticContract,
    *,
    stream_run_id: str,
    batch_ingestor: BatchIngestor,
    source_view_prefix: str = "cf_stream_batch",
    evidence: EvidenceWriter | None = None,
    query_one: QueryOne | None = None,
    runtime_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute an available-now stream and process micro-batches through an injected ingestor."""

    source = contract.source.raw or {}
    interpreted_source = interpret_incremental_files_source(source) if is_incremental_file_source(source) else source
    checkpoint = interpreted_source.get("progress_location") or interpreted_source.get("checkpoint_location")
    if not checkpoint:
        raise ValueError("available-now stream requires source.progress_location or source.checkpoint_location")

    started = datetime.now(timezone.utc)
    batch_results: list[dict[str, Any]] = []
    stream_df = resolve_source_dataframe(spark, source)
    status = "SUCCESS"
    error_message = None
    if evidence is not None:
        evidence.write_stream_log(
            stream_start_payload(
                contract,
                stream_run_id=stream_run_id,
                status="RUNNING",
                started_at_utc=started,
                runtime_metadata=runtime_metadata,
            )
        )

    def process_batch(batch_df: Any, batch_id: int) -> None:
        view_name = f"{source_view_prefix}_{stream_run_id}_{batch_id}".replace("-", "_")
        batch_df.createOrReplaceTempView(view_name)
        prepared = PreparedInput(
            source_view=view_name,
            source_columns=tuple(str(column) for column in getattr(batch_df, "columns", ()) or ()),
            rows_read=int(batch_df.count()) if hasattr(batch_df, "count") else 0,
            source_name=str(source.get("path") or source.get("table") or contract.source.name),
            source_metadata={"stream_run_id": stream_run_id, "batch_id": batch_id},
        )
        result = batch_ingestor(prepared, batch_id)
        batch_results.append(result)
        if result.get("status") == "FAILED":
            raise RuntimeError(f"Available-now stream batch {batch_id} failed: {result.get('error_message')}")

    try:
        query = (
            stream_df.writeStream.foreachBatch(process_batch)
            .option("checkpointLocation", str(checkpoint))
            .trigger(availableNow=True)
            .start()
        )
        query.awaitTermination()
    except Exception as exc:
        status = "FAILED"
        error_message = str(exc)
    local_metrics = stream_metrics_from_batches(batch_results)
    child_metrics = _child_stream_metrics(evidence, query_one, stream_run_id)
    metrics = child_metrics if child_metrics and prefer_child_stream_metrics(local_metrics, child_metrics) else local_metrics
    result = stream_result_payload(
        contract,
        stream_run_id=stream_run_id,
        status=status,
        started_at_utc=started,
        batch_results=batch_results,
        error_message=error_message,
        stream_metrics=metrics,
        runtime_metadata=runtime_metadata,
    )
    if evidence is not None:
        evidence.finish_stream_log(stream_run_id=stream_run_id, payload=result)
        if status == "FAILED":
            evidence.write_error_log(_stream_error_payload(contract, stream_run_id, result, error_message))
    return result


def _child_stream_metrics(
    evidence: EvidenceWriter | None,
    query_one: QueryOne | None,
    stream_run_id: str,
) -> dict[str, int] | None:
    if evidence is None or query_one is None:
        return None
    row = query_one(
        render_stream_child_run_metrics_sql(
            stream_run_id=stream_run_id,
            runs_table=f"{evidence.catalog}.{evidence.schema}.ctrl_ingestion_runs",
        )
    )
    if not row:
        return None
    return {
        "batches_processed": int(row.get("batches_processed") or 0),
        "total_rows_read": int(row.get("total_rows_read") or 0),
        "total_rows_written": int(row.get("total_rows_written") or 0),
        "total_rows_quarantined": int(row.get("total_rows_quarantined") or 0),
    }


def _stream_error_payload(
    contract: SemanticContract,
    stream_run_id: str,
    result: dict[str, Any],
    error_message: str | None,
) -> dict[str, Any]:
    source = contract.source.raw or {}
    return {
        "run_id": stream_run_id,
        "error_ts_utc": result.get("ended_at_utc"),
        "error_date": str(result.get("ended_at_utc") or "")[:10],
        "target_table": result.get("target_table"),
        "source_table": source.get("path") or source.get("table") or contract.source.name,
        "mode": contract.write.mode,
        "status": result.get("status"),
        "error_type": "AvailableNowStreamError",
        "error_message": error_message,
        "stack_trace": error_message,
    }
