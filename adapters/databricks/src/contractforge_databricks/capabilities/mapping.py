"""Map Databricks-native capabilities to ContractForge Core capabilities."""

from __future__ import annotations

from contractforge_core.capabilities import PlatformCapabilities
from contractforge_databricks.capabilities.models import DatabricksCapabilities
from contractforge_databricks.write_modes.registry import list_write_modes


def to_core_capabilities(capabilities: DatabricksCapabilities) -> PlatformCapabilities:
    review_required = []
    if capabilities.status("lakeflow_auto_cdc") == "unknown":
        review_required.append("lakeflow_auto_cdc")

    return PlatformCapabilities(
        platform="databricks",
        supports_append=capabilities.supports("delta_tables"),
        supports_overwrite=capabilities.supports("delta_tables"),
        supports_merge=capabilities.supports("sql_merge"),
        supports_hash_diff=capabilities.supports("sql_merge"),
        supports_scd2=capabilities.supports("sql_merge"),
        supports_snapshot_soft_delete=capabilities.supports("snapshot_soft_delete_merge"),
        supports_schema_evolution=capabilities.supports("delta_tables"),
        supports_row_filters=capabilities.supports("uc_row_filters"),
        supports_column_masks=capabilities.supports("uc_column_masks"),
        supports_available_now_streaming=capabilities.supports("autoloader_cloudfiles"),
        supports_required_columns_quality=True,
        supports_unique_key_quality=True,
        supports_max_null_ratio_quality=True,
        supports_expression_quality=True,
        supports_shape=capabilities.supports("databricks_runtime"),
        supports_transform=capabilities.supports("databricks_runtime"),
        evidence_stores=("delta_control_tables",) if capabilities.supports("delta_control_tables") else (),
        review_required_semantics=tuple(review_required),
        supported_custom_write_modes=list_write_modes(),
    )
