"""Capability declaration for the AWS Glue Iceberg adapter target."""

from __future__ import annotations

from contractforge_core.capabilities import PlatformCapabilities

AWS_SUBTARGET_GLUE_ICEBERG = "aws_glue_iceberg"


def glue_iceberg_capabilities() -> PlatformCapabilities:
    """Return conservative core capabilities for the initial AWS target.

    Some capabilities are marked as supported while also listed in
    ``review_required_semantics``. This tells the core planner that AWS has
    plausible native primitives, but the adapter is not yet allowed to claim
    automatic semantic equivalence.
    """

    return PlatformCapabilities(
        platform=AWS_SUBTARGET_GLUE_ICEBERG,
        supports_append=True,
        supports_overwrite=True,
        supports_merge=True,
        supports_hash_diff=True,
        supports_scd2=True,
        supports_snapshot_soft_delete=True,
        supports_schema_evolution=True,
        supports_row_filters=True,
        supports_column_masks=True,
        supports_available_now_streaming=True,
        supports_required_columns_quality=True,
        supports_unique_key_quality=True,
        supports_max_null_ratio_quality=True,
        supports_expression_quality=True,
        supports_shape=True,
        supports_transform=True,
        evidence_stores=("iceberg_table",),
        review_required_semantics=(
            "scd2_historical",
            "snapshot_soft_delete",
            "row_filters",
            "column_masks",
            "source.native_passthrough",
        ),
    )
