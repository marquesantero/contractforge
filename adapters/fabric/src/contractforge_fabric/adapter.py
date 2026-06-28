"""ContractForge adapter implementation for Microsoft Fabric targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.planner import PlanningResult, plan_contract
from contractforge_core.semantic import SemanticContract
from contractforge_fabric.capabilities import FABRIC_SUBTARGET_LAKEHOUSE, fabric_lakehouse_capabilities
from contractforge_fabric.diagnostics import fabric_planning_warnings, unsupported_source_blockers
from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.rendering import render_fabric_review_artifacts


@dataclass(frozen=True)
class FabricAdapter:
    """Fabric Lakehouse adapter for planning and review artifact rendering."""

    declared_capabilities: PlatformCapabilities
    environment: FabricEnvironment = FabricEnvironment()
    name: str = FABRIC_SUBTARGET_LAKEHOUSE

    @classmethod
    def lakehouse(cls, environment: dict[str, Any] | None = None) -> "FabricAdapter":
        return cls(
            fabric_lakehouse_capabilities(),
            environment=FabricEnvironment.from_contract(environment),
        )

    def capabilities(self) -> PlatformCapabilities:
        return self.declared_capabilities

    def plan(self, contract: SemanticContract) -> PlanningResult:
        source_blockers = unsupported_source_blockers(contract)
        if source_blockers:
            return PlanningResult(status="UNSUPPORTED", plan=None, blockers=source_blockers)

        result = plan_contract(contract, self.capabilities())
        warnings = result.warnings + fabric_planning_warnings(contract)
        if result.status == "SUPPORTED":
            return PlanningResult(status="SUPPORTED_WITH_WARNINGS", plan=result.plan, warnings=warnings)
        return PlanningResult(
            status=result.status,
            plan=result.plan,
            blockers=result.blockers,
            warnings=warnings,
        )

    def render_contract(self, contract: SemanticContract, *, raw_contract: dict[str, Any] | None = None) -> RenderedArtifacts:
        planning = self.plan(contract)
        return render_fabric_review_artifacts(
            plan=planning.plan,
            planning=planning,
            contract=contract,
            raw_contract=raw_contract,
            environment=self.environment,
        )
