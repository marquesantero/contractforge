"""High-level Fabric adapter API."""

from __future__ import annotations

from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.planner import PlanningResult
from contractforge_fabric.capabilities import FABRIC_SUBTARGET_LAKEHOUSE
from contractforge_fabric.subtargets import adapter_for_subtarget


def plan_fabric_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = FABRIC_SUBTARGET_LAKEHOUSE,
    environment: dict[str, Any] | None = None,
) -> PlanningResult:
    semantic = semantic_contract_from_mapping(contract)
    adapter = adapter_for_subtarget(subtarget, environment=environment)
    return adapter.plan(semantic)


def render_fabric_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = FABRIC_SUBTARGET_LAKEHOUSE,
    environment: dict[str, Any] | None = None,
) -> RenderedArtifacts:
    semantic = semantic_contract_from_mapping(contract)
    adapter = adapter_for_subtarget(subtarget, environment=environment)
    return adapter.render_contract(semantic, raw_contract=contract)


__all__ = ["plan_fabric_contract", "render_fabric_contract"]
