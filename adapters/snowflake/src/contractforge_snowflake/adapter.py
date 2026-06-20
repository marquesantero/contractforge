"""ContractForge adapter implementation for Snowflake targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.planner import ExecutionPlan, PlanningResult, plan_contract
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.capabilities import (
    SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE,
    snowflake_sql_warehouse_capabilities,
)
from contractforge_snowflake.diagnostics import (
    snowflake_planning_warnings,
    snowflake_review_required_warnings,
    unsupported_source_blockers,
)
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.rendering import render_snowflake_review_artifacts


@dataclass(frozen=True)
class SnowflakeAdapter:
    """Snowflake adapter for planning and publish-bundle preparation."""

    declared_capabilities: PlatformCapabilities
    environment: SnowflakeEnvironment = SnowflakeEnvironment()
    name: str = SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE

    @classmethod
    def sql_warehouse(cls, environment: dict[str, Any] | None = None) -> "SnowflakeAdapter":
        return cls(
            snowflake_sql_warehouse_capabilities(),
            environment=SnowflakeEnvironment.from_contract(environment),
        )

    def capabilities(self) -> PlatformCapabilities:
        return self.declared_capabilities

    def plan(self, contract: SemanticContract) -> PlanningResult:
        source_blockers = unsupported_source_blockers(contract)
        if source_blockers:
            return PlanningResult(status="UNSUPPORTED", plan=None, blockers=source_blockers)

        result = plan_contract(contract, self.capabilities())
        warnings = result.warnings + snowflake_planning_warnings(contract)
        review_warnings = snowflake_review_required_warnings(contract)
        if review_warnings and result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}:
            return PlanningResult(
                status="REVIEW_REQUIRED",
                plan=result.plan,
                blockers=result.blockers,
                warnings=warnings + review_warnings,
            )
        if warnings and result.status == "SUPPORTED":
            return PlanningResult(status="SUPPORTED_WITH_WARNINGS", plan=result.plan, warnings=warnings)
        return PlanningResult(
            status=result.status,
            plan=result.plan,
            blockers=result.blockers,
            warnings=warnings + review_warnings,
        )

    def render(self, plan: ExecutionPlan) -> RenderedArtifacts:
        return render_snowflake_review_artifacts(plan=plan, planning=None, environment=self.environment)

    def render_contract(self, contract: SemanticContract, *, raw_contract: dict[str, Any] | None = None) -> RenderedArtifacts:
        planning = self.plan(contract)
        return render_snowflake_review_artifacts(
            plan=planning.plan,
            planning=planning,
            contract=contract,
            raw_contract=raw_contract,
            environment=self.environment,
        )
