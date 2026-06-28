"""ContractForge adapter implementation for AWS targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.planner import PlanningResult, plan_contract
from contractforge_core.semantic import SemanticContract
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG, glue_iceberg_capabilities
from contractforge_aws.contract_extensions import aws_extension_warnings
from contractforge_aws.diagnostics import aws_planning_warnings, unsupported_source_blockers
from contractforge_aws.environment import AWSEnvironment
from contractforge_aws.rendering import render_aws_review_artifacts


@dataclass(frozen=True)
class AWSAdapter:
    """AWS adapter for Glue/Iceberg planning and artifact rendering.

    AWS SDK calls remain optional runtime helpers. The base adapter path stays
    deterministic and SDK-free.
    """

    declared_capabilities: PlatformCapabilities
    environment: AWSEnvironment = AWSEnvironment()
    name: str = AWS_SUBTARGET_GLUE_ICEBERG

    @classmethod
    def glue_iceberg(cls, environment: dict[str, Any] | None = None) -> "AWSAdapter":
        return cls(glue_iceberg_capabilities(), environment=AWSEnvironment.from_contract(environment))

    def capabilities(self) -> PlatformCapabilities:
        return self.declared_capabilities

    def plan(self, contract: SemanticContract) -> PlanningResult:
        source_blockers = unsupported_source_blockers(contract)
        if source_blockers:
            return PlanningResult(status="UNSUPPORTED", plan=None, blockers=source_blockers)

        result = plan_contract(contract, self.capabilities())
        aws_warnings = aws_planning_warnings(contract) + aws_extension_warnings(contract)
        if not aws_warnings:
            return result
        warnings = result.warnings + aws_warnings
        if result.status == "SUPPORTED":
            return PlanningResult(status="SUPPORTED_WITH_WARNINGS", plan=result.plan, warnings=warnings)
        return PlanningResult(status=result.status, plan=result.plan, blockers=result.blockers, warnings=warnings)

    def render_contract(self, contract: SemanticContract) -> RenderedArtifacts:
        planning = self.plan(contract)
        return render_aws_review_artifacts(
            plan=planning.plan,
            planning=planning,
            contract=contract,
            environment=self.environment,
        )
