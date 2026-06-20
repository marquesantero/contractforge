"""Capability factory helpers."""

from __future__ import annotations

from contractforge_core.capabilities import NativeCapability, capability


def uc_sql_capability(name: str, *, is_uc_target: bool, is_databricks: bool) -> NativeCapability:
    if not is_uc_target:
        return capability(
            name,
            "unsupported",
            "Unity Catalog governance capability requires a three-part target table name.",
            requires=("Unity Catalog", "catalog.schema.table"),
        )
    if is_databricks:
        return capability(
            name,
            "supported",
            "Unity Catalog SQL governance capability is eligible for this Databricks target.",
            requires=("Unity Catalog privileges",),
        )
    return capability(
        name,
        "unknown",
        "Target is Unity Catalog-shaped, but Databricks runtime evidence was not detected.",
        requires=("Unity Catalog privileges",),
    )


def workspace_capability(
    name: str,
    *,
    is_databricks: bool,
    is_uc_target: bool,
    reason: str,
    requires: tuple[str, ...],
) -> NativeCapability:
    if not is_databricks:
        return capability(name, "unsupported", f"{reason} Databricks runtime evidence was not detected.", requires=requires)
    if not is_uc_target:
        return capability(name, "unknown", f"{reason} Target/catalog context is incomplete.", requires=requires)
    return capability(name, "unknown", f"{reason} Workspace configuration and permissions were not probed.", requires=requires)
