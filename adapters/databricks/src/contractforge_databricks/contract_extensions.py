"""Databricks contract extension utilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from contractforge_core.planner import PlanningWarning

DATABRICKS_EXTENSION_FIELDS = {
    "allow_type_widening",
    "autoloader",
    "cache_source",
    "cluster_columns",
    "delta_properties",
    "encoding",
    "encoding_columns",
    "explain_format",
    "explain_mode",
    "fix_encoding",
    "hooks",
    "lakeflow",
    "lock_enabled",
    "merge_partition_column",
    "merge_strategy",
    "openlineage_enabled",
    "openlineage_namespace",
    "openlineage_producer",
    "optimize_after_write",
    "partition_column",
    "partition_columns",
    "partition_value",
    "replace_partitions_source_complete",
    "write_engine",
    "zorder_columns",
}


def normalize_databricks_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Return a defensive copy of a Databricks contract mapping.

    Databricks-owned execution fields must be declared explicitly under
    ``extensions.databricks``. The adapter does not translate top-level aliases.
    """

    return deepcopy(contract)


def databricks_extensions(contract: Any) -> dict[str, Any]:
    extensions = getattr(contract, "extensions", None)
    if not isinstance(extensions, dict):
        return {}
    value = extensions.get("databricks")
    return dict(value) if isinstance(value, dict) else {}


def databricks_extension_warnings(contract: Any) -> tuple[PlanningWarning, ...]:
    """Return warnings for Databricks extension keys the adapter will ignore."""

    unknown = sorted(set(databricks_extensions(contract)) - DATABRICKS_EXTENSION_FIELDS)
    return tuple(
        PlanningWarning(
            code="DATABRICKS_UNKNOWN_EXTENSION",
            message=(
                f"extensions.databricks.{name} is not a recognized Databricks adapter extension "
                "and will not be honored by planning, rendering or runtime execution."
            ),
        )
        for name in unknown
    )
