"""Platform-neutral evidence record models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RunEvidenceRecord:
    run_id: str
    target_table: str
    mode: str
    status: str
    started_at_utc: datetime
    finished_at_utc: datetime | None = None
    metrics: dict[str, Any] | None = None


@dataclass(frozen=True)
class ErrorEvidenceRecord:
    run_id: str
    target_table: str
    error_class: str
    error_message: str
    occurred_at_utc: datetime


@dataclass(frozen=True)
class LineageEvidenceRecord:
    run_id: str
    target_table: str
    source_name: str
    event: dict[str, Any]
    event_time_utc: datetime


@dataclass(frozen=True)
class QualityEvidenceRecord:
    run_id: str
    target_table: str
    rule_name: str
    status: str
    observed_value: str
    checked_at_utc: datetime


@dataclass(frozen=True)
class SchemaChangeEvidenceRecord:
    run_id: str
    target_table: str
    change_type: str
    payload: dict[str, Any]
    changed_at_utc: datetime


@dataclass(frozen=True)
class CostEvidenceRecord:
    run_id: str
    target_table: str
    signal_name: str
    signal_value: float
    payload: dict[str, Any]
    captured_at_utc: datetime


@dataclass(frozen=True)
class QuarantineEvidenceRecord:
    run_id: str
    target_table: str
    record_ref: str
    reason: str
    quarantined_at_utc: datetime


@dataclass(frozen=True)
class SourceMetadataEvidenceRecord:
    run_id: str
    target_table: str
    source_metadata: dict[str, Any]
    captured_at_utc: datetime


@dataclass(frozen=True)
class StreamBatchEvidenceRecord:
    run_id: str
    target_table: str
    batch_id: str
    batch_metrics: dict[str, Any]
    captured_at_utc: datetime


@dataclass(frozen=True)
class AccessEvidenceRecord:
    run_id: str
    target_table: str
    action: str
    status: str
    payload: dict[str, Any]
    applied_at_utc: datetime
