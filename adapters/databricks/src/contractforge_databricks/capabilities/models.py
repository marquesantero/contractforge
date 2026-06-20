"""Databricks-native capability evidence models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_core.capabilities import (
    CapabilityEvidence as CapabilityEvidence,
    CapabilityStatus,
    NativeCapability,
)

RuntimeKind = Literal["databricks_serverless", "databricks_classic", "spark", "unknown"]


@dataclass(frozen=True)
class DatabricksCapabilities:
    runtime_kind: RuntimeKind
    target_table: str | None
    spark_version: str | None
    capabilities: dict[str, NativeCapability] = field(default_factory=dict)

    def supports(self, name: str) -> bool:
        capability = self.capabilities.get(name)
        return bool(capability and capability.supported)

    def status(self, name: str) -> CapabilityStatus:
        capability = self.capabilities.get(name)
        return "unknown" if capability is None else capability.status

    def unsupported(self) -> list[NativeCapability]:
        return [item for item in self.capabilities.values() if item.status == "unsupported"]

    def unknown(self) -> list[NativeCapability]:
        return [item for item in self.capabilities.values() if item.status == "unknown"]

    def as_dict(self) -> dict[str, Any]:
        return {
            "runtime_kind": self.runtime_kind,
            "target_table": self.target_table,
            "spark_version": self.spark_version,
            "capabilities": {name: item.as_dict() for name, item in self.capabilities.items()},
        }
