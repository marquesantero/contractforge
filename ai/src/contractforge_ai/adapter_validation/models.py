"""Models for deterministic adapter planning validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_ai.models import EvidenceItem, Finding

AdapterValidationStatus = Literal["READY", "NEEDS_DECISIONS", "INVALID"]


@dataclass(frozen=True)
class AdapterPlanningOutcome:
    """Result of planning one contract through one optional platform adapter."""

    adapter: str
    status: AdapterValidationStatus
    summary: str
    findings: list[Finding] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    raw_status: str | None = None
    artifact_names: list[str] = field(default_factory=list)
    artifact_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "status": self.status,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
            "evidence": [item.to_dict() for item in self.evidence],
            **({"raw_status": self.raw_status} if self.raw_status else {}),
            **({"artifact_names": self.artifact_names} if self.artifact_names else {}),
            **({"artifact_types": self.artifact_types} if self.artifact_types else {}),
        }
