"""Databricks run evidence payload assembly."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contractforge_core.config import CTRL_SCHEMA_VERSION, FRAMEWORK_VERSION
from contractforge_core.runtime import PreparedInput
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.runtime.metadata import contract_metadata
from contractforge_databricks.runtime.models import DatabricksIngestOptions
from contractforge_databricks.runtime.write_strategy import write_strategy_evidence


def run_payload(
    contract: SemanticContract,
    prepared: PreparedInput,
    opts: DatabricksIngestOptions,
    run_id: str,
    target: str,
    status: str,
    started: str,
    finished: str,
    rows_written: int,
    quality_status_value: str,
    operation_metrics: dict[str, Any],
    schema_changes: dict[str, Any],
    governance_results: dict[str, Any],
    write_started_at: str | None,
    write_finished_at: str | None,
    stage_durations: dict[str, float],
    watermark_column: str | None,
    watermark_previous: str | None,
    watermark_current: str | None,
    diagnostics: dict[str, bool],
    error_message: str | None,
    skip_reason: str | None,
    skipped_by_run_id: str | None,
) -> dict[str, Any]:
    runtime = dict(opts.runtime_metadata or {})
    source_metadata = dict(prepared.source_metadata or {})
    operations = dict(contract.operations.metadata or {}) if contract.operations and contract.operations.metadata else {}
    annotations_result = governance_results.get("annotations") or {}
    operations_result = governance_results.get("operations") or {}
    row_metrics = _row_metrics(operation_metrics, rows_written)
    delta_version_after = _metric_int(operation_metrics, "version", default=None)
    write_strategy = write_strategy_evidence(contract, target, runtime)
    return {
        "run_id": run_id,
        "run_ts_utc": started,
        "run_date": _date_now(),
        "started_at_utc": started,
        "finished_at_utc": finished,
        "duration_seconds": _duration_seconds(started, finished),
        "target_table": target,
        "runtime_entrypoint": runtime.get("notebook_name"),
        "layer": contract.target.layer,
        "mode": contract.write.mode,
        "write_engine_requested": write_strategy["write_engine_requested"],
        "write_engine_selected": write_strategy["write_engine_selected"],
        "write_engine_status": write_strategy["write_engine_status"],
        "write_engine_reason": write_strategy["write_engine_reason"],
        "write_engine_fallback_policy": write_strategy["write_engine_fallback_policy"],
        "write_engine": dict(write_strategy),
        "status": status,
        "source_table": prepared.source_name or prepared.source_view,
        "source_type": source_metadata.get("source_type"),
        "source_connector": source_metadata.get("source_connector"),
        "source_name": source_metadata.get("source_name") or prepared.source_name,
        "source_system": source_metadata.get("source_system") or _source_system(contract),
        "source_provider": source_metadata.get("source_provider"),
        "source_format": source_metadata.get("source_format"),
        "source_path": source_metadata.get("source_path"),
        "source_options_json": _metadata_value(source_metadata, "source_options", "source_options_redacted"),
        "source_read_json": _metadata_value(source_metadata, "source_read", "source_read_redacted"),
        "source_request_json": _metadata_value(source_metadata, "source_request", "source_request_redacted"),
        "source_auth_json": _metadata_value(source_metadata, "source_auth", "source_auth_redacted"),
        "source_pagination_json": _metadata_value(source_metadata, "source_pagination", "source_pagination_redacted"),
        "source_response_json": _metadata_value(source_metadata, "source_response", "source_response_redacted"),
        "source_incremental_json": _metadata_value(source_metadata, "source_incremental", "source_incremental_redacted"),
        "source_limits_json": _metadata_value(source_metadata, "source_limits", "source_limits_redacted"),
        "source_capabilities_json": source_metadata.get("source_capabilities"),
        "source_metrics_json": source_metadata.get("source_metrics"),
        "source": source_metadata or None,
        "rows_read": prepared.rows_read,
        "rows_effective": prepared.rows_read - prepared.rows_quarantined,
        "rows_written": rows_written,
        "rows_inserted": row_metrics["rows_inserted"],
        "rows_updated": row_metrics["rows_updated"],
        "rows_deleted": row_metrics["rows_deleted"],
        "rows_expired": row_metrics["rows_expired"],
        "rows_quarantined": prepared.rows_quarantined,
        "watermark_column": watermark_column,
        "watermark_previous": watermark_previous,
        "watermark_current": watermark_current,
        "quality_status": quality_status_value,
        "schema_changes": schema_changes,
        "schema_changes_json": schema_changes,
        "stage_durations": stage_durations,
        "stage_durations_json": stage_durations,
        "operation_metrics": operation_metrics,
        "operation_metrics_json": operation_metrics,
        "metrics_json": operation_metrics,
        "schema_policy": contract.write.schema_policy,
        "applied_presets": operations.get("applied_presets"),
        "metrics_source": operation_metrics.get("metrics_source") or "adapter_runtime",
        "table_version_after": None if delta_version_after is None else str(delta_version_after),
        "write_delta_version": delta_version_after,
        "write_committed": status == "SUCCESS" and rows_written >= 0,
        "explain_captured": bool(diagnostics.get("explain_captured")),
        "openlineage_event_emitted": bool(diagnostics.get("openlineage_event_emitted")),
        "runtime_type": runtime.get("runtime_type"),
        "engine_version": runtime.get("spark_version"),
        "python_version": runtime.get("python_version"),
        "framework_version": FRAMEWORK_VERSION,
        "ctrl_schema_version": CTRL_SCHEMA_VERSION,
        "contract_owner": contract.governance.owner if contract.governance else None,
        "contract_domain": contract.target.domain,
        "contract_tags_json": operations.get("tags"),
        "contract_sla": operations.get("sla"),
        "runtime_parameters_json": operations.get("runtime_parameters"),
        "contract_metadata": contract_metadata(contract, operations),
        "annotations_status": annotations_result.get("status"),
        "annotations_result_json": annotations_result or None,
        "operations_json": {"metadata": operations, "record_result": operations_result} if operations or operations_result else None,
        "idempotency_key": opts.idempotency_key,
        "idempotency_policy": opts.idempotency_policy,
        "write_started_at_utc": write_started_at,
        "write_finished_at_utc": write_finished_at,
        "parent_run_id": operations.get("parent_run_id"),
        "run_group_id": operations.get("run_group_id"),
        "master_job_id": operations.get("master_job_id"),
        "master_run_id": operations.get("master_run_id"),
        "skip_reason": skip_reason,
        "skipped_by_run_id": skipped_by_run_id,
        "error_message": error_message,
    }


def _date_now() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _metadata_value(source_metadata: dict[str, Any], raw_key: str, redacted_key: str) -> Any:
    return source_metadata.get(redacted_key) if redacted_key in source_metadata else source_metadata.get(raw_key)


def _source_system(contract: SemanticContract) -> str | None:
    value = (contract.source.raw or {}).get("system")
    return str(value) if value not in (None, "") else None


def _row_metrics(operation_metrics: dict[str, Any], rows_written: int) -> dict[str, int]:
    return {
        "rows_inserted": _metric_int(operation_metrics, "rows_inserted", default=rows_written),
        "rows_updated": _metric_int(operation_metrics, "rows_updated"),
        "rows_deleted": _metric_int(operation_metrics, "rows_deleted"),
        "rows_expired": _metric_int(operation_metrics, "rows_expired"),
    }


def _metric_int(metrics: dict[str, Any], key: str, *, default: int | None = 0) -> int | None:
    value = metrics.get(key, default)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _duration_seconds(started: str, finished: str) -> float | None:
    try:
        started_dt = datetime.strptime(started, "%Y-%m-%d %H:%M:%S")
        finished_dt = datetime.strptime(finished, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return (finished_dt - started_dt).total_seconds()
