"""Platform-neutral quality result normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

QualitySeverity = Literal["abort", "quarantine", "warn"]
QualityStatus = Literal["PASSED", "FAILED", "WARNED", "QUARANTINED", "NOT_CONFIGURED"]
QualityFailAction = Literal["fail", "quarantine", "warn"]


@dataclass(frozen=True)
class QualityRuleResult:
    rule_name: str
    status: QualityStatus
    failed_count: int = 0
    severity: QualitySeverity = "quarantine"
    message: str | None = None
    details: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "status": self.status,
            "severity": self.severity,
            "failed_count": self.failed_count,
            "message": self.message,
            "details": self.details or {},
        }


def quality_status(results: tuple[QualityRuleResult, ...]) -> QualityStatus:
    """Severity-only aggregate status; does not consider the on_quality_fail policy."""

    if not results:
        return "NOT_CONFIGURED"
    failures = tuple(result for result in results if result.failed_count > 0)
    if not failures:
        return "PASSED"
    if all(result.severity == "warn" for result in failures):
        return "WARNED"
    return "FAILED"


def quality_policy_status(
    results: tuple[QualityRuleResult, ...],
    *,
    on_quality_fail: str | None,
) -> QualityStatus:
    """Aggregate status reflecting the on_quality_fail policy that was applied.

    Behaves like quality_status() with one additional resolution: when every
    failed rule has severity 'warn' or 'quarantine' and on_quality_fail is
    'quarantine', the status is QUARANTINED instead of FAILED, because the
    declared policy successfully removed the offending rows rather than
    aborting the run.
    """

    base = quality_status(results)
    if base != "FAILED":
        return base
    policy = str(on_quality_fail or "fail").strip().lower()
    if policy != "quarantine":
        return base
    failures = tuple(result for result in results if result.failed_count > 0)
    if all(result.severity in {"warn", "quarantine"} for result in failures):
        return "QUARANTINED"
    return base


def quarantinable_results(results: tuple[QualityRuleResult, ...]) -> tuple[QualityRuleResult, ...]:
    return tuple(result for result in results if result.failed_count > 0 and result.severity == "quarantine")
