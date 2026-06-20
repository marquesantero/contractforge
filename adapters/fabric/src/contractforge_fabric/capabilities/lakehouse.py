"""Capability declaration for the Microsoft Fabric Lakehouse adapter target."""

from __future__ import annotations

from contractforge_core.capabilities import PlatformCapabilities

FABRIC_SUBTARGET_LAKEHOUSE = "fabric_lakehouse"


def fabric_lakehouse_capabilities() -> PlatformCapabilities:
    """Return conservative capabilities for the initial Fabric target.

    Fabric has native Lakehouse, Warehouse, OneLake, notebook and Data Factory
    surfaces. This adapter has planning, review artifacts and an explicit
    Notebook smoke workflow, so execution-sensitive semantics remain
    review-required until full bronze-to-gold runtime evidence exists.
    """

    return PlatformCapabilities(
        platform=FABRIC_SUBTARGET_LAKEHOUSE,
        supports_append=True,
        supports_overwrite=True,
        supports_merge=True,
        supports_hash_diff=True,
        supports_scd2=True,
        supports_snapshot_soft_delete=True,
        supports_schema_evolution=True,
        supports_row_filters=False,
        supports_column_masks=False,
        supports_available_now_streaming=False,
        supports_required_columns_quality=True,
        supports_unique_key_quality=True,
        supports_max_null_ratio_quality=True,
        supports_expression_quality=True,
        supports_shape=True,
        supports_transform=True,
        evidence_stores=("fabric_lakehouse_delta_tables",),
        review_required_semantics=(
            "available_now_streaming",
            "row_filters",
            "column_masks",
            "source.jdbc",
            "source.rest_api.authenticated",
            "source.http_file.authenticated",
            "source.kafka_bounded",
            "source.eventhubs_bounded",
            "source.native_passthrough",
        ),
    )
