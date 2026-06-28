"""ContractForge Core adapter implementation for Databricks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.planner import PlanningResult, plan_contract
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.capabilities import DatabricksCapabilities, evaluate_databricks_capabilities, to_core_capabilities
from contractforge_databricks.contract_extensions import databricks_extension_warnings
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.rendering import render_databricks_artifacts


@dataclass(frozen=True)
class DatabricksAdapter:
    """Dry-planning Databricks adapter.

    Execution belongs in a later runtime module. This adapter only declares
    capabilities, plans via the core, and renders reviewable native artifacts.
    """

    native_capabilities: DatabricksCapabilities
    environment: DatabricksEnvironment = DatabricksEnvironment()
    name: str = "databricks"

    @classmethod
    def from_evidence(
        cls,
        *,
        target_table: str | None = None,
        runtime_type: str | None = None,
        spark_version: str | None = None,
        spark_conf: dict[str, str] | None = None,
        environment: dict[str, Any] | None = None,
    ) -> "DatabricksAdapter":
        env = DatabricksEnvironment.from_contract(environment)
        return cls(
            evaluate_databricks_capabilities(
                target_table=target_table,
                runtime_type=runtime_type or env.runtime_kind,
                spark_version=spark_version,
                spark_conf=spark_conf,
            ),
            environment=env,
        )

    def capabilities(self) -> PlatformCapabilities:
        return to_core_capabilities(self.native_capabilities)

    def plan(self, contract: SemanticContract) -> PlanningResult:
        result = plan_contract(contract, self.capabilities())
        extension_warnings = databricks_extension_warnings(contract)
        if not extension_warnings:
            return result
        warnings = result.warnings + extension_warnings
        if result.status == "SUPPORTED":
            return PlanningResult(status="SUPPORTED_WITH_WARNINGS", plan=result.plan, blockers=result.blockers, warnings=warnings)
        return PlanningResult(status=result.status, plan=result.plan, blockers=result.blockers, warnings=warnings)

    def render_contract(self, contract: SemanticContract) -> RenderedArtifacts:
        planning = self.plan(contract)
        return render_databricks_artifacts(contract, planning, self.native_capabilities, environment=self.environment)
