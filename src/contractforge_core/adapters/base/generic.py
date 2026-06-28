"""Generic in-memory adapters useful for tests and dry planning."""

from __future__ import annotations

from dataclasses import dataclass

from contractforge_core.adapters.base.protocol import RenderedArtifacts
from contractforge_core.capabilities.models import PlatformCapabilities
from contractforge_core.planner import PlanningResult, plan_contract
from contractforge_core.semantic.models import SemanticContract


@dataclass(frozen=True)
class CapabilitiesAdapter:
    """Small adapter backed only by a capability declaration."""

    name: str
    declared_capabilities: PlatformCapabilities

    def capabilities(self) -> PlatformCapabilities:
        return self.declared_capabilities

    def plan(self, contract: SemanticContract) -> PlanningResult:
        return plan_contract(contract, self.declared_capabilities)

    def render_contract(self, contract: SemanticContract) -> RenderedArtifacts:
        planning = plan_contract(contract, self.declared_capabilities)
        lines = [
            f"# Execution plan for {self.declared_capabilities.platform}",
            "",
            "| Step | Intent |",
            "| --- | --- |",
        ]
        if planning.plan is not None:
            lines.extend(f"| {step.name} | {step.intent} |" for step in planning.plan.steps)
        return RenderedArtifacts(artifacts={"review.md": "\n".join(lines) + "\n"})


def full_feature_adapter() -> CapabilitiesAdapter:
    capabilities = PlatformCapabilities(
        platform="full-feature-generic",
        supports_append=True,
        supports_overwrite=True,
        supports_merge=True,
        supports_hash_diff=True,
        supports_scd2=True,
        supports_snapshot_soft_delete=True,
        supports_schema_evolution=True,
        supports_row_filters=True,
        supports_column_masks=True,
        supports_available_now_streaming=True,
        evidence_stores=("audit_tables",),
    )
    return CapabilitiesAdapter(name=capabilities.platform, declared_capabilities=capabilities)


def append_only_adapter() -> CapabilitiesAdapter:
    capabilities = PlatformCapabilities(
        platform="append-only-generic",
        supports_append=True,
        evidence_stores=("audit_files",),
    )
    return CapabilitiesAdapter(name=capabilities.platform, declared_capabilities=capabilities)

