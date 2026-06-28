"""ContractForge adapter implementation for Google Cloud targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.planner import PlanningResult, plan_contract
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.capabilities import GCP_SUBTARGET_BIGQUERY, gcp_bigquery_capabilities
from contractforge_gcp.diagnostics import gcp_planning_warnings, source_review_required, unsupported_source_blockers
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering import render_gcp_bigquery_artifacts


@dataclass(frozen=True)
class GCPAdapter:
    """GCP BigQuery adapter for planning and render artifact generation."""

    declared_capabilities: PlatformCapabilities
    environment: GCPEnvironment = GCPEnvironment()
    name: str = GCP_SUBTARGET_BIGQUERY

    @classmethod
    def bigquery(cls, environment: dict[str, Any] | None = None) -> "GCPAdapter":
        return cls(gcp_bigquery_capabilities(), environment=GCPEnvironment.from_contract(environment))

    def capabilities(self) -> PlatformCapabilities:
        return self.declared_capabilities

    def plan(self, contract: SemanticContract) -> PlanningResult:
        source_blockers = unsupported_source_blockers(contract)
        if source_blockers:
            return PlanningResult(status="UNSUPPORTED", plan=None, blockers=source_blockers)
        result = plan_contract(contract, self.capabilities())
        warnings = result.warnings + gcp_planning_warnings(contract)
        if result.status == "SUPPORTED" and source_review_required(contract):
            return PlanningResult(status="REVIEW_REQUIRED", plan=result.plan, warnings=warnings)
        if result.status == "SUPPORTED":
            return PlanningResult(status="SUPPORTED_WITH_WARNINGS", plan=result.plan, warnings=warnings)
        return PlanningResult(status=result.status, plan=result.plan, blockers=result.blockers, warnings=warnings)

    def render_contract(self, contract: SemanticContract, *, raw_contract: dict[str, Any] | None = None) -> RenderedArtifacts:
        planning = self.plan(contract)
        return render_gcp_bigquery_artifacts(
            plan=planning.plan,
            planning=planning,
            contract=contract,
            raw_contract=raw_contract,
            environment=self.environment,
        )
