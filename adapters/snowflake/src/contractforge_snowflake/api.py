"""High-level Snowflake adapter API."""

from __future__ import annotations

from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.planner import PlanningResult
from contractforge_snowflake.capabilities import SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE
from contractforge_snowflake.subtargets import adapter_for_subtarget


def plan_snowflake_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE,
    environment: dict[str, Any] | None = None,
) -> PlanningResult:
    semantic = semantic_contract_from_mapping(contract)
    adapter = adapter_for_subtarget(subtarget, environment=environment)
    return adapter.plan(semantic)


def render_snowflake_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE,
    environment: dict[str, Any] | None = None,
) -> RenderedArtifacts:
    return build_snowflake_publish_bundle(contract, subtarget=subtarget, environment=environment)


def build_snowflake_publish_bundle(
    contract: dict[str, Any],
    *,
    subtarget: str = SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE,
    environment: dict[str, Any] | None = None,
) -> RenderedArtifacts:
    """Build Snowflake publish artifacts for the stable library runner."""

    semantic = semantic_contract_from_mapping(contract)
    adapter = adapter_for_subtarget(subtarget, environment=environment)
    return adapter.render_contract(semantic, raw_contract=contract)


__all__ = [
    "build_snowflake_publish_bundle",
    "plan_snowflake_contract",
    "render_snowflake_contract",
]
