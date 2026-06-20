"""Platform-neutral evidence model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

EvidenceEventType = Literal[
    "run",
    "error",
    "quality_result",
    "quarantined_record_reference",
    "schema_change",
    "lineage_event",
    "source_metadata",
    "stream_batch",
    "governance_application",
    "cost_signal",
]


@dataclass(frozen=True)
class EvidenceEvent:
    event_type: EvidenceEventType
    run_id: str
    target: str
    occurred_at_utc: datetime
    payload: dict[str, Any]


@dataclass(frozen=True)
class EvidenceRequirement:
    required: bool = True
    event_types: tuple[EvidenceEventType, ...] = (
        "run",
        "error",
        "quality_result",
        "schema_change",
        "lineage_event",
    )

