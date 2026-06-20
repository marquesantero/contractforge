"""Platform-neutral adapter operation result models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GovernanceApplyStatus = Literal["SUCCESS", "WARNED", "FAILED", "IGNORED", "VALIDATED", "NOT_CONFIGURED"]
OperationsRecordStatus = Literal["RECORDED", "FAILED", "NOT_CONFIGURED"]


@dataclass(frozen=True)
class GovernanceApplyResult:
    status: GovernanceApplyStatus
    applied: int = 0
    failed: int = 0
    validated: int = 0
    ignored: int = 0
    sql_preview: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperationsRecordResult:
    status: OperationsRecordStatus
    sql: str | None = None
    error: str | None = None
