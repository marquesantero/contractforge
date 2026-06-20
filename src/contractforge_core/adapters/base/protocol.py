"""Base adapter protocol for platform-specific implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from contractforge_core.capabilities.models import PlatformCapabilities
from contractforge_core.planner.result import ExecutionPlan, PlanningResult
from contractforge_core.semantic.models import SemanticContract


@dataclass(frozen=True)
class RenderedArtifacts:
    artifacts: dict[str, str]


class PlatformAdapter(Protocol):
    name: str

    def capabilities(self) -> PlatformCapabilities:
        ...

    def plan(self, contract: SemanticContract) -> PlanningResult:
        ...

    def render(self, plan: ExecutionPlan) -> RenderedArtifacts:
        ...

