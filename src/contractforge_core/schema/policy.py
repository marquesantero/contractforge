"""Platform-neutral schema policy planning models."""

from __future__ import annotations

from dataclasses import dataclass

from contractforge_core.semantic import SchemaPolicy


@dataclass(frozen=True)
class SchemaPolicyPlan:
    policy: SchemaPolicy
    writer_options: dict[str, str]
    preflight_required: bool
    reason: str
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "policy": self.policy,
            "writer_options": dict(self.writer_options),
            "preflight_required": self.preflight_required,
            "reason": self.reason,
            "warnings": list(self.warnings),
        }
