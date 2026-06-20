"""Portability classification for semantic concepts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contractforge_core.config import canonical_write_mode

PortabilityClass = Literal["PORTABLE", "PLATFORM_SPECIFIC", "SUPPORTED_WITH_WARNINGS", "REVIEW_REQUIRED", "UNSUPPORTED"]


@dataclass(frozen=True)
class PortabilityBoundary:
    concept: str
    classification: PortabilityClass
    reason: str


WRITE_MODE_BOUNDARIES: dict[str, PortabilityBoundary] = {
    "scd0_append": PortabilityBoundary("scd0_append", "PORTABLE", "Append is broadly portable with append capability."),
    "scd0_overwrite": PortabilityBoundary(
        "scd0_overwrite",
        "SUPPORTED_WITH_WARNINGS",
        "Overwrite is portable only when replacement scope and atomicity are preserved.",
    ),
    "scd1_upsert": PortabilityBoundary(
        "scd1_upsert",
        "SUPPORTED_WITH_WARNINGS",
        "SCD1 is a general intent but requires merge/upsert semantics.",
    ),
    "scd1_hash_diff": PortabilityBoundary(
        "scd1_hash_diff",
        "SUPPORTED_WITH_WARNINGS",
        "Hash-diff change detection must be implemented consistently by the adapter.",
    ),
    "scd2_historical": PortabilityBoundary(
        "scd2_historical",
        "REVIEW_REQUIRED",
        "Historical semantics vary across engines and require explicit SCD2 capability.",
    ),
    "snapshot_soft_delete": PortabilityBoundary(
        "snapshot_soft_delete",
        "REVIEW_REQUIRED",
        "Snapshot reconciliation and soft delete semantics are platform-sensitive.",
    ),
}


def classify_write_mode(mode: str) -> PortabilityBoundary:
    normalized = canonical_write_mode(mode)
    return WRITE_MODE_BOUNDARIES.get(
        normalized,
        PortabilityBoundary(normalized, "UNSUPPORTED", "Unknown write mode."),
    )
