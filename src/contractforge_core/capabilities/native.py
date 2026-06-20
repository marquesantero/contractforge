"""Platform-neutral native capability evidence models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CapabilityStatus = Literal["supported", "unsupported", "unknown"]


@dataclass(frozen=True)
class CapabilityEvidence:
    source: str
    message: str
    value: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"source": self.source, "message": self.message, "value": self.value}
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class NativeCapability:
    name: str
    status: CapabilityStatus
    reason: str
    evidence: tuple[CapabilityEvidence, ...] = ()
    requires: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.status == "supported"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "supported": self.supported,
            "reason": self.reason,
            "requires": list(self.requires),
            "evidence": [item.as_dict() for item in self.evidence],
        }


def capability(
    name: str,
    status: CapabilityStatus,
    reason: str,
    *,
    evidence: tuple[CapabilityEvidence, ...] = (),
    requires: tuple[str, ...] = (),
) -> NativeCapability:
    return NativeCapability(name=name, status=status, reason=reason, evidence=evidence, requires=requires)
