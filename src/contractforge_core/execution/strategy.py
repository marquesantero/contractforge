"""Platform-neutral write strategy model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WriteStrategy:
    kind: str
    engine: str
    reason: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return self.kind != "unsupported"

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "engine": self.engine,
            "reason": self.reason,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
        }
