"""High-level GCP adapter API."""

from __future__ import annotations

from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.planner import PlanningResult
from contractforge_gcp.capabilities import GCP_SUBTARGET_BIGQUERY
from contractforge_gcp.subtargets import adapter_for_subtarget


def plan_gcp_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = GCP_SUBTARGET_BIGQUERY,
    environment: dict[str, Any] | None = None,
) -> PlanningResult:
    semantic = semantic_contract_from_mapping(contract)
    adapter = adapter_for_subtarget(subtarget, environment=environment)
    return adapter.plan(semantic)


def render_gcp_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = GCP_SUBTARGET_BIGQUERY,
    environment: dict[str, Any] | None = None,
) -> RenderedArtifacts:
    semantic = semantic_contract_from_mapping(contract)
    adapter = adapter_for_subtarget(subtarget, environment=environment)
    return adapter.render_contract(semantic, raw_contract=contract)


__all__ = ["plan_gcp_contract", "render_gcp_contract"]
