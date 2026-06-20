"""Quality rule enforcement partitioning for AWS Glue Data Quality."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from contractforge_core.semantic import QualityIntent
from contractforge_aws.quality.dqdl import is_row_level_quarantinable

_ABORT = "abort"
_QUARANTINE = "quarantine"


@dataclass(frozen=True)
class QualityRulePartition:
    abort: tuple[QualityIntent, ...]
    quarantine: tuple[QualityIntent, ...]
    recorded: tuple[QualityIntent, ...]


@dataclass(frozen=True)
class QualityBucketRule:
    bucket: str
    condition: Callable[[QualityIntent], bool]


def partition_quality_rules(rules: Sequence[QualityIntent]) -> QualityRulePartition:
    buckets: dict[str, list[QualityIntent]] = {"abort": [], "quarantine": [], "recorded": []}
    for rule in rules:
        buckets[_bucket_for(rule)].append(rule)
    return QualityRulePartition(
        abort=tuple(buckets["abort"]),
        quarantine=tuple(buckets["quarantine"]),
        recorded=tuple(buckets["recorded"]),
    )


def _bucket_for(rule: QualityIntent) -> str:
    return next((item.bucket for item in _BUCKET_RULES if item.condition(rule)), "recorded")


_BUCKET_RULES = (
    QualityBucketRule("abort", lambda rule: rule.severity == _ABORT),
    QualityBucketRule("quarantine", lambda rule: rule.severity == _QUARANTINE and is_row_level_quarantinable(rule)),
)
