"""Planner checks for non-write semantic capabilities."""

from __future__ import annotations

from contractforge_core.capabilities.models import PlatformCapabilities
from contractforge_core.planner.result import PlanningBlocker, PlanningWarning
from contractforge_core.semantic.models import SemanticContract


def match_quality(
    contract: SemanticContract,
    capabilities: PlatformCapabilities,
    blockers: list[PlanningBlocker],
    review_markers: list[str],
) -> None:
    review_required = set(capabilities.review_required_semantics)
    for quality in contract.quality:
        if quality.rule in {"not_null", "accepted_values", "row_count_minimum"}:
            continue
        semantic = f"quality_rules.{quality.rule}"
        if semantic in review_required:
            review_markers.append(semantic)
            continue
        if quality.rule == "required_columns" and not capabilities.supports_required_columns_quality:
            blockers.append(PlanningBlocker("QUALITY_REQUIRED_COLUMNS_UNSUPPORTED", "Required-column quality checks are not supported."))
        elif quality.rule == "unique_key" and not capabilities.supports_unique_key_quality:
            blockers.append(PlanningBlocker("QUALITY_UNIQUE_KEY_UNSUPPORTED", "Unique-key quality checks are not supported."))
        elif quality.rule == "max_null_ratio" and not capabilities.supports_max_null_ratio_quality:
            blockers.append(PlanningBlocker("QUALITY_MAX_NULL_RATIO_UNSUPPORTED", "Max-null-ratio quality checks are not supported."))
        elif quality.rule == "expression" and not capabilities.supports_expression_quality:
            blockers.append(PlanningBlocker("QUALITY_EXPRESSION_UNSUPPORTED", "Expression quality checks require adapter-declared expression support."))


def match_preparation(
    contract: SemanticContract,
    capabilities: PlatformCapabilities,
    blockers: list[PlanningBlocker],
    warnings: list[PlanningWarning],
    review_markers: list[str],
) -> None:
    review_required = set(capabilities.review_required_semantics)
    if contract.shape:
        if "shape" in review_required:
            review_markers.append("shape")
        elif not capabilities.supports_shape:
            blockers.append(PlanningBlocker("SHAPE_UNSUPPORTED", "Shape intent requires adapter-declared shape support."))
    if contract.transform:
        if "transform" in review_required:
            review_markers.append("transform")
        elif not capabilities.supports_transform:
            warnings.append(
                PlanningWarning(
                    "TRANSFORM_SUPPORT_UNKNOWN",
                    "Transform intent requires adapter-declared transform support for execution.",
                )
            )
