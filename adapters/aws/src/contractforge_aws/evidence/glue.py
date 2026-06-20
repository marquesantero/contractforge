"""Map AWS Glue JobRun payloads into ContractForge evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from contractforge_core.evidence import CostEvidenceRecord, RunEvidenceRecord


@dataclass(frozen=True)
class GlueJobRunEvidence:
    run: RunEvidenceRecord
    cost: CostEvidenceRecord | None
    operation_metrics: dict[str, Any]


def glue_job_run_evidence(
    job_run: dict[str, Any],
    *,
    target_table: str,
    mode: str,
    captured_at_utc: datetime | None = None,
) -> GlueJobRunEvidence:
    captured = _utc(captured_at_utc or datetime.now(timezone.utc))
    run_id = str(job_run.get("Id") or job_run.get("JobRunId") or "")
    if not run_id:
        raise ValueError("AWS Glue JobRun payload requires Id or JobRunId")
    started_at = _datetime_value(job_run.get("StartedOn")) or captured
    completed_at = _datetime_value(job_run.get("CompletedOn"))
    state = str(job_run.get("JobRunState") or "UNKNOWN")
    operation_metrics = _operation_metrics(job_run)
    run = RunEvidenceRecord(
        run_id=run_id,
        target_table=target_table,
        mode=mode,
        status=_contractforge_status(state),
        started_at_utc=started_at,
        finished_at_utc=completed_at,
        metrics={
            "metrics_source": "glue_jobrun",
            "runtime_type": "aws_glue",
            "master_job_id": job_run.get("JobName"),
            "master_run_id": run_id,
            "duration_seconds": _duration_seconds(job_run),
            "operation_metrics_json": operation_metrics,
            "error_message": job_run.get("ErrorMessage") or job_run.get("StateDetail"),
        },
    )
    cost = None
    dpu_seconds = job_run.get("DPUSeconds")
    if dpu_seconds not in (None, ""):
        cost = CostEvidenceRecord(
            run_id=run_id,
            target_table=target_table,
            signal_name="glue_dpu_seconds",
            signal_value=float(dpu_seconds),
            payload=operation_metrics,
            captured_at_utc=captured,
        )
    return GlueJobRunEvidence(run=run, cost=cost, operation_metrics=operation_metrics)


def _operation_metrics(job_run: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "Id",
        "JobName",
        "JobRunState",
        "StartedOn",
        "CompletedOn",
        "ExecutionTime",
        "DPUSeconds",
        "WorkerType",
        "NumberOfWorkers",
        "MaxCapacity",
        "ExecutionClass",
        "Attempt",
        "TriggerName",
        "ErrorMessage",
        "StateDetail",
    )
    return {key: _json_value(job_run[key]) for key in keys if key in job_run and job_run[key] is not None}


def _contractforge_status(state: str) -> str:
    normalized = state.upper()
    if normalized == "SUCCEEDED":
        return "SUCCESS"
    if normalized in {"FAILED", "TIMEOUT", "STOPPED", "ERROR", "EXPIRED"}:
        return "FAILED"
    if normalized in {"STARTING", "RUNNING", "STOPPING", "WAITING"}:
        return "RUNNING"
    return normalized or "UNKNOWN"


def _duration_seconds(job_run: dict[str, Any]) -> int | None:
    execution_time = job_run.get("ExecutionTime")
    if execution_time not in (None, ""):
        return int(execution_time)
    started = _datetime_value(job_run.get("StartedOn"))
    completed = _datetime_value(job_run.get("CompletedOn"))
    if started and completed:
        return int((completed - started).total_seconds())
    return None


def _datetime_value(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _utc(value)
    text = str(value).strip()
    if not text:
        return None
    return _utc(datetime.fromisoformat(text.replace("Z", "+00:00")))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    return value
