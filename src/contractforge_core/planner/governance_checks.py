"""Planner checks for governance and operational semantics."""

from __future__ import annotations

from contractforge_core.capabilities.models import PlatformCapabilities
from contractforge_core.planner.result import PlanningBlocker
from contractforge_core.semantic.models import SemanticContract


def match_governance(
    contract: SemanticContract,
    capabilities: PlatformCapabilities,
    blockers: list[PlanningBlocker],
    review_markers: list[str],
) -> None:
    governance = contract.governance
    if governance is None:
        return

    review_required = set(capabilities.review_required_semantics)
    if governance.row_filters and "row_filters" in review_required:
        review_markers.append("row_filters")
    elif governance.row_filters and not capabilities.supports_row_filters:
        blockers.append(PlanningBlocker("ROW_FILTERS_UNSUPPORTED", "Row filters are not supported."))

    if governance.column_masks and "column_masks" in review_required:
        review_markers.append("column_masks")
    elif governance.column_masks and not capabilities.supports_column_masks:
        blockers.append(PlanningBlocker("COLUMN_MASKS_UNSUPPORTED", "Column masks are not supported."))


def match_operations(
    contract: SemanticContract,
    capabilities: PlatformCapabilities,
    blockers: list[PlanningBlocker],
    review_markers: list[str],
) -> None:
    operations = contract.operations
    if operations is None or not operations.available_now_streaming:
        return

    if "available_now_streaming" in capabilities.review_required_semantics:
        review_markers.append("available_now_streaming")
    elif not capabilities.supports_available_now_streaming:
        blockers.append(
            PlanningBlocker(
                "AVAILABLE_NOW_UNSUPPORTED",
                "Available-now streaming requires bounded streaming capability.",
            )
        )
