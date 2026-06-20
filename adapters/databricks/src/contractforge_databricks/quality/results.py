"""Compatibility exports for platform-neutral quality result models."""

from contractforge_core.quality import (
    QualityRuleResult,
    QualitySeverity,
    QualityStatus,
    quality_status,
    quarantinable_results,
)

__all__ = [
    "QualityRuleResult",
    "QualitySeverity",
    "QualityStatus",
    "quality_status",
    "quarantinable_results",
]
