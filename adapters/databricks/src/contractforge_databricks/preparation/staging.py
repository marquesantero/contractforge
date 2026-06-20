"""Compatibility exports for platform-neutral staging specifications."""

from contractforge_core.preparation import (
    HashDiffStageSpec,
    SCD2StageSpec,
    SnapshotStageSpec,
    scd2_stage_spec_from_contract,
    snapshot_stage_spec_from_contract,
)

__all__ = [
    "HashDiffStageSpec",
    "SCD2StageSpec",
    "SnapshotStageSpec",
    "scd2_stage_spec_from_contract",
    "snapshot_stage_spec_from_contract",
]
