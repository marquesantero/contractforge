"""Capability matching for portable semantic contracts."""

from __future__ import annotations

from contractforge_core.capabilities.models import PlatformCapabilities
from contractforge_core.planner.governance_checks import match_governance, match_operations
from contractforge_core.planner.plan_builder import build_execution_plan
from contractforge_core.planner.result import PlanningBlocker, PlanningResult, PlanningWarning
from contractforge_core.planner.semantic_checks import match_preparation, match_quality
from contractforge_core.planner.write_checks import match_evidence, match_schema_policy, match_write_mode
from contractforge_core.semantic.models import SemanticContract


def plan_contract(
    contract: SemanticContract,
    capabilities: PlatformCapabilities,
) -> PlanningResult:
    blockers: list[PlanningBlocker] = []
    warnings: list[PlanningWarning] = []
    review_markers: list[str] = []

    match_write_mode(contract, capabilities, blockers, review_markers)
    match_schema_policy(contract, capabilities, warnings)
    match_quality(contract, capabilities, blockers, review_markers)
    match_preparation(contract, capabilities, blockers, warnings, review_markers)
    match_governance(contract, capabilities, blockers, review_markers)
    match_operations(contract, capabilities, blockers, review_markers)
    match_evidence(contract, capabilities, blockers)

    if blockers:
        return PlanningResult(
            status="UNSUPPORTED",
            plan=None,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    plan = build_execution_plan(contract, capabilities)

    if review_markers:
        return PlanningResult(
            status="REVIEW_REQUIRED",
            plan=plan,
            warnings=tuple(warnings) + _review_warnings(review_markers),
        )

    if warnings:
        return PlanningResult(status="SUPPORTED_WITH_WARNINGS", plan=plan, warnings=tuple(warnings))

    return PlanningResult(status="SUPPORTED", plan=plan)


def _review_warnings(review_markers: list[str]) -> tuple[PlanningWarning, ...]:
    return tuple(
        PlanningWarning(
            code="REVIEW_REQUIRED",
            message=f"Semantic requires platform review: {marker}.",
        )
        for marker in review_markers
    )
