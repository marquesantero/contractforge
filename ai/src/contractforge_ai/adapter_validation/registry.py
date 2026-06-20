"""Registry of optional ContractForge adapter planning APIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdapterPlannerSpec:
    """Import target for one adapter's public planning function."""

    name: str
    module: str
    function: str
    render_function: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


DEFAULT_ADAPTER_PLANNERS: dict[str, AdapterPlannerSpec] = {
    "aws": AdapterPlannerSpec(
        name="aws",
        module="contractforge_aws.api",
        function="plan_aws_contract",
        render_function="render_aws_contract",
    ),
    "databricks": AdapterPlannerSpec(
        name="databricks",
        module="contractforge_databricks.api",
        function="plan_databricks_contract",
        render_function="render_databricks_contract",
    ),
    "fabric": AdapterPlannerSpec(
        name="fabric",
        module="contractforge_fabric.api",
        function="plan_fabric_contract",
        render_function="render_fabric_contract",
    ),
    "gcp": AdapterPlannerSpec(
        name="gcp",
        module="contractforge_gcp.api",
        function="plan_gcp_contract",
        render_function="render_gcp_contract",
    ),
    "snowflake": AdapterPlannerSpec(
        name="snowflake",
        module="contractforge_snowflake.api",
        function="plan_snowflake_contract",
        render_function="render_snowflake_contract",
    ),
}


def adapter_planner_spec(adapter: str) -> AdapterPlannerSpec | None:
    """Return the planner spec for a supported optional adapter name."""

    return DEFAULT_ADAPTER_PLANNERS.get(adapter.strip().lower())


def known_adapter_names() -> tuple[str, ...]:
    """Return adapter names known by the AI deterministic validation registry."""

    return tuple(sorted(DEFAULT_ADAPTER_PLANNERS))
