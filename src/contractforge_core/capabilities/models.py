"""Platform capability declarations consumed by the semantic planner."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformCapabilities:
    platform: str
    supports_append: bool = False
    supports_overwrite: bool = False
    supports_merge: bool = False
    supports_hash_diff: bool = False
    supports_scd2: bool = False
    supports_snapshot_soft_delete: bool = False
    supports_schema_evolution: bool = False
    supports_row_filters: bool = False
    supports_column_masks: bool = False
    supports_available_now_streaming: bool = False
    supports_required_columns_quality: bool = True
    supports_unique_key_quality: bool = True
    supports_max_null_ratio_quality: bool = True
    supports_expression_quality: bool = False
    supports_shape: bool = False
    supports_transform: bool = False
    evidence_stores: tuple[str, ...] = ()
    review_required_semantics: tuple[str, ...] = ()
    supported_custom_write_modes: tuple[str, ...] = ()
