"""Capability declaration for the Google Cloud BigQuery adapter target."""

from __future__ import annotations

from contractforge_core.capabilities import PlatformCapabilities
from contractforge_gcp.sources import review_required_gcp_source_types

GCP_SUBTARGET_BIGQUERY = "gcp_bigquery"


def gcp_bigquery_capabilities() -> PlatformCapabilities:
    """Return conservative capabilities for the initial BigQuery target."""

    review_required_sources = tuple(f"source.{source_type}" for source_type in review_required_gcp_source_types())
    return PlatformCapabilities(
        platform=GCP_SUBTARGET_BIGQUERY,
        supports_append=True,
        supports_overwrite=True,
        supports_merge=True,
        supports_hash_diff=False,
        supports_scd2=False,
        supports_snapshot_soft_delete=False,
        supports_schema_evolution=False,
        supports_row_filters=False,
        supports_column_masks=False,
        supports_available_now_streaming=False,
        supports_required_columns_quality=True,
        supports_unique_key_quality=True,
        supports_max_null_ratio_quality=True,
        supports_expression_quality=True,
        supports_shape=False,
        supports_transform=False,
        evidence_stores=("bigquery_audit_tables",),
        review_required_semantics=(
            "available_now_streaming",
            "row_filters",
            "column_masks",
            "scd1_hash_diff",
            "scd2_historical",
            "snapshot_soft_delete",
            *review_required_sources,
        ),
    )
