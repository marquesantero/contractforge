"""Platform-neutral quality result models."""

from contractforge_core.quality.rules import ABORT_ONLY_RULES, is_abort_only_failure
from contractforge_core.quality.results import (
    QualityFailAction,
    QualityRuleResult,
    QualitySeverity,
    QualityStatus,
    quality_policy_status,
    quality_status,
    quarantinable_results,
)

__all__ = [
    "QualityFailAction",
    "QualityRuleResult",
    "QualitySeverity",
    "QualityStatus",
    "ABORT_ONLY_RULES",
    "is_abort_only_failure",
    "quality_policy_status",
    "quality_status",
    "quarantinable_results",
]
