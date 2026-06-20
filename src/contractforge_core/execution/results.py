"""Platform-neutral execution result models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ExecutionStatus = Literal["SUCCESS", "FAILED", "SKIPPED"]


@dataclass(frozen=True)
class ExecutionOutcome:
    status: ExecutionStatus
    operation: str
    target: str
    metrics: dict[str, Any]
    sql: str | None = None
    message: str | None = None
