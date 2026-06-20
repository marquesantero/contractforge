"""Runtime payload helpers for Databricks available-now streaming."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contractforge_core.config import CTRL_SCHEMA_VERSION, FRAMEWORK_VERSION
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.rendering.names import target_full_name


def stream_metrics_from_batches(batch_results: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate metrics returned by child batch ingestions."""

    return {
        "batches_processed": len(batch_results),
        "total_rows_read": sum(_int_metric(result, "rows_read") for result in batch_results),
        "total_rows_written": sum(_int_metric(result, "rows_written") for result in batch_results),
        "total_rows_quarantined": sum(_int_metric(result, "rows_quarantined") for result in batch_results),
    }


def prefer_child_stream_metrics(local: dict[str, int], child: dict[str, int]) -> bool:
    """Return true when persisted child-run metrics are more complete."""

    if child.get("batches_processed", 0) <= 0:
        return False
    local_rows = local.get("total_rows_read", 0) + local.get("total_rows_written", 0) + local.get("total_rows_quarantined", 0)
    child_rows = child.get("total_rows_read", 0) + child.get("total_rows_written", 0) + child.get("total_rows_quarantined", 0)
    return local.get("batches_processed", 0) == 0 or child.get("batches_processed", 0) > local.get("batches_processed", 0) or child_rows > local_rows


def stream_start_payload(
    contract: SemanticContract,
    *,
    stream_run_id: str,
    status: str = "RUNNING",
    started_at_utc: datetime | None = None,
    idempotency_key: str | None = None,
    idempotency_policy: str = "always_run",
    runtime_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = contract.source.raw or {}
    operations = _operations_metadata(contract)
    runtime = runtime_metadata or {}
    return {
        "stream_run_id": stream_run_id,
        "idempotency_key": idempotency_key if idempotency_key is not None else operations.get("idempotency_key"),
        "idempotency_policy": operations.get("idempotency_policy") or idempotency_policy,
        "target_table": target_full_name(contract),
        "target_catalog": _target_catalog(contract),
        "target_layer": contract.target.layer,
        "runtime_entrypoint": runtime.get("notebook_name") or operations.get("notebook_name"),
        "source_type": source.get("type") or contract.source.kind,
        "source_path": source.get("path") or source.get("url") or source.get("table") or contract.source.location,
        "trigger": source.get("trigger") or "available_now",
        "checkpoint_location": source.get("progress_location") or source.get("checkpoint_location"),
        "status": status,
        "started_at_utc": _timestamp(started_at_utc),
        "batches_processed": 0,
        "total_rows_read": 0,
        "total_rows_written": 0,
        "total_rows_quarantined": 0,
        "framework_version": FRAMEWORK_VERSION,
        "ctrl_schema_version": CTRL_SCHEMA_VERSION,
        "master_job_id": operations.get("master_job_id"),
        "master_run_id": operations.get("master_run_id"),
        "parent_run_id": operations.get("parent_run_id"),
        "run_group_id": operations.get("run_group_id"),
        **runtime,
    }


def stream_result_payload(
    contract: SemanticContract,
    *,
    stream_run_id: str,
    status: str,
    started_at_utc: datetime,
    batch_results: list[dict[str, Any]],
    stage_durations: dict[str, float] | None = None,
    error_message: str | None = None,
    skip_reason: str | None = None,
    skipped_by_stream_run_id: str | None = None,
    stream_metrics: dict[str, int] | None = None,
    runtime_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    finished = datetime.now(timezone.utc)
    metrics = stream_metrics or stream_metrics_from_batches(batch_results)
    return {
        **stream_start_payload(
            contract,
            stream_run_id=stream_run_id,
            status=status,
            started_at_utc=started_at_utc,
            runtime_metadata=runtime_metadata,
        ),
        "ended_at_utc": _timestamp(finished),
        "duration_seconds": (finished - started_at_utc).total_seconds(),
        "batches_processed": metrics["batches_processed"],
        "total_rows_read": metrics["total_rows_read"],
        "total_rows_written": metrics["total_rows_written"],
        "total_rows_quarantined": metrics["total_rows_quarantined"],
        "batch_results": batch_results,
        "stage_durations": stage_durations or {},
        "error_message": error_message,
        "skip_reason": skip_reason,
        "skipped_by_stream_run_id": skipped_by_stream_run_id,
    }


def _int_metric(payload: dict[str, Any], key: str) -> int:
    return int(payload.get(key) or 0)


def _timestamp(value: datetime | None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _operations_metadata(contract: SemanticContract) -> dict[str, Any]:
    return dict(contract.operations.metadata or {}) if contract.operations and contract.operations.metadata else {}


def _target_catalog(contract: SemanticContract) -> str | None:
    if not contract.target.namespace:
        return None
    return contract.target.namespace.split(".", 1)[0]
