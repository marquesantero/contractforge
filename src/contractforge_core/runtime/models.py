"""Platform-neutral runtime input models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from contractforge_core.execution import ExecutionOutcome


class QueryOne(Protocol):
    def __call__(self, statement: str) -> dict[str, Any] | None:
        ...


@dataclass(frozen=True)
class QuarantineReference:
    record_ref: str
    reason: str
    rule_name: str | None = None


@dataclass(frozen=True)
class PreparedInput:
    source_view: str
    source_columns: tuple[str, ...] = ()
    source_schema: dict[str, str] | None = None
    rows_read: int = 0
    rows_quarantined: int = 0
    source_name: str | None = None
    source_metadata: dict[str, Any] | None = None
    quarantine_records: tuple[QuarantineReference, ...] = ()


def rows_written_from_outcome(prepared: PreparedInput, outcome: ExecutionOutcome | None) -> int:
    if outcome and isinstance(outcome.metrics.get("rows_written"), int):
        return int(outcome.metrics["rows_written"])
    return prepared.rows_read - prepared.rows_quarantined
