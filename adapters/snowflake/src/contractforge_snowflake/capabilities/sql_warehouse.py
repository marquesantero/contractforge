"""Capability declaration for the Snowflake SQL warehouse adapter target."""

from __future__ import annotations

from contractforge_core.capabilities import PlatformCapabilities

SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE = "snowflake_sql_warehouse"
SNOWFLAKE_SUBTARGET_TASK_GRAPH = "snowflake_task_graph"
SNOWFLAKE_SUBTARGET_SNOWPIPE = "snowflake_snowpipe"
SNOWFLAKE_SUBTARGET_STREAMS_TASKS = "snowflake_streams_tasks"


def snowflake_sql_warehouse_capabilities() -> PlatformCapabilities:
    """Return conservative capabilities for the first Snowflake target."""

    return PlatformCapabilities(
        platform=SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE,
        supports_append=True,
        supports_overwrite=True,
        supports_merge=True,
        supports_hash_diff=True,
        supports_scd2=False,
        supports_snapshot_soft_delete=False,
        supports_schema_evolution=True,
        supports_row_filters=True,
        supports_column_masks=True,
        supports_available_now_streaming=False,
        supports_required_columns_quality=True,
        supports_unique_key_quality=True,
        supports_max_null_ratio_quality=True,
        supports_expression_quality=True,
        supports_shape=True,
        supports_transform=True,
        evidence_stores=("snowflake_audit_tables",),
        review_required_semantics=(
            "scd2_historical",
            "snapshot_soft_delete",
            "available_now_streaming",
            "source.incremental_files",
            "source.kafka_bounded",
            "source.eventhubs_bounded",
            "source.http_file",
            "source.jdbc",
            "source.native_passthrough",
        ),
    )
