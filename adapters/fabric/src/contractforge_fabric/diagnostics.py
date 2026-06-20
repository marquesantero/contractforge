"""Fabric planning diagnostics."""

from __future__ import annotations

from contractforge_core.planner import PlanningBlocker, PlanningWarning
from contractforge_core.semantic import SemanticContract
from contractforge_fabric.sources import classify_fabric_source


def unsupported_source_blockers(contract: SemanticContract) -> tuple[PlanningBlocker, ...]:
    classification = classify_fabric_source(contract.source.raw)
    if classification.status != "UNSUPPORTED":
        return ()
    return (
        PlanningBlocker(
            code="FABRIC_UNSUPPORTED_SOURCE",
            message=f"Fabric Lakehouse adapter has no declared source mapping for `{classification.source_type}`.",
        ),
    )


def fabric_planning_warnings(contract: SemanticContract) -> tuple[PlanningWarning, ...]:
    warnings: list[PlanningWarning] = []
    classification = classify_fabric_source(contract.source.raw)
    if classification.status in {"SUPPORTED_WITH_WARNINGS", "REVIEW_REQUIRED"}:
        warnings.append(
            PlanningWarning(
                code="FABRIC_SOURCE_REVIEW",
                message=f"`{classification.source_type}` maps to {classification.native_mapping or 'Fabric review'}: {classification.note}",
            )
        )
    warnings.append(
        PlanningWarning(
            code="FABRIC_RUNTIME_PARITY_PENDING",
            message=(
                "Fabric planning/rendering is available and the explicit smoke workflow can deploy and submit "
                "generated notebooks, but full bronze-to-gold runtime parity is not validated yet."
            ),
        )
    )
    return tuple(warnings)
