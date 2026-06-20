"""Databricks write strategy selection.

This module is the single decision point for choosing Databricks-native
features versus a ContractForge-compatible algorithm.
"""

from __future__ import annotations

from typing import Literal

from contractforge_core.execution import WriteStrategy
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.capabilities.models import DatabricksCapabilities
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.parity import scenarios_for_engine, scenarios_for_mode
from contractforge_databricks.write_modes.registry import get_write_mode

StrategyKind = Literal["native_databricks", "contractforge_algorithm", "unsupported"]


def choose_write_strategy(
    contract: SemanticContract,
    capabilities: DatabricksCapabilities,
) -> WriteStrategy:
    requested = _requested_engine(contract)
    if requested:
        explicit = _explicit_strategy(contract, capabilities, requested)
        if explicit is not None:
            return explicit
    mode = contract.write.mode

    if mode == "scd0_append":
        return _delta_strategy(capabilities, engine="delta_append", reason="Delta append is the native Databricks path.")
    if mode == "scd0_overwrite":
        return _delta_strategy(
            capabilities,
            engine="delta_overwrite",
            reason="Delta overwrite is the native Databricks path when replacement scope is explicit.",
        )
    if mode == "scd1_upsert":
        if capabilities.supports("sql_merge"):
            scenario_count = len(scenarios_for_engine("databricks_sql_merge"))
            return WriteStrategy(
                "native_databricks",
                "databricks_sql_merge",
                f"Databricks SQL MERGE has {scenario_count} documented SCD1 parity scenarios.",
            )
        return WriteStrategy("unsupported", "databricks_sql_merge", "SCD1 requires Delta MERGE.", blockers=("sql_merge",))
    if mode == "scd1_hash_diff":
        if capabilities.supports("delta_tables"):
            return WriteStrategy(
                "contractforge_algorithm",
                "core_managed_hash_diff_delta",
                "Databricks has no single native hash-diff write mode; use the ContractForge algorithm over Delta.",
            )
        return WriteStrategy("unsupported", "core_managed_hash_diff_delta", "Hash diff requires Delta table support.", blockers=("delta_tables",))
    if mode == "scd2_historical":
        if capabilities.status("lakeflow_auto_cdc") == "supported":
            scenario_count = len(scenarios_for_mode("scd2_historical"))
            return WriteStrategy(
                "native_databricks",
                "lakeflow_auto_cdc",
                f"Lakeflow AUTO CDC has {scenario_count} documented SCD2 review scenarios.",
                warnings=("requires Lakeflow compatibility validation",),
            )
        if capabilities.supports("sql_merge"):
            return WriteStrategy(
                "contractforge_algorithm",
                "core_managed_scd2_delta_merge",
                "Use ContractForge SCD2 Delta MERGE algorithm because Lakeflow equivalence is not proven.",
            )
        return WriteStrategy("unsupported", "core_managed_scd2_delta_merge", "SCD2 requires Delta MERGE.", blockers=("sql_merge",))
    if mode == "snapshot_soft_delete":
        if capabilities.supports("snapshot_soft_delete_merge"):
            return WriteStrategy(
                "contractforge_algorithm",
                "core_managed_snapshot_soft_delete_delta_merge",
                "Use ContractForge soft-delete algorithm to avoid Lakeflow hard-delete semantic mismatch.",
            )
        return WriteStrategy(
            "unsupported",
            "core_managed_snapshot_soft_delete_delta_merge",
            "Snapshot soft delete requires Delta MERGE with NOT MATCHED BY SOURCE.",
            blockers=("snapshot_soft_delete_merge",),
        )
    if mode.startswith("custom:") and get_write_mode(mode):
        return WriteStrategy(
            "contractforge_algorithm",
            mode,
            "Adapter-owned custom write mode registered for Databricks runtime execution.",
            warnings=("custom write modes are not portable core semantics",),
        )

    return WriteStrategy("unsupported", "unknown", f"Unsupported write mode: {mode}", blockers=("write_mode",))


def _delta_strategy(capabilities: DatabricksCapabilities, *, engine: str, reason: str) -> WriteStrategy:
    if capabilities.supports("delta_tables"):
        return WriteStrategy("native_databricks", engine, reason)
    return WriteStrategy("unsupported", engine, "Delta table support is required.", blockers=("delta_tables",))


def _explicit_strategy(
    contract: SemanticContract,
    capabilities: DatabricksCapabilities,
    requested: str,
) -> WriteStrategy | None:
    fallback_policy = _fallback_policy(contract)
    normalized = _normalize_engine(requested)
    if normalized in {"auto", "delta", "core_managed"}:
        return None
    if normalized == "databricks_sql_merge":
        if contract.write.mode == "scd1_upsert" and capabilities.supports("sql_merge"):
            return WriteStrategy(
                "native_databricks",
                "databricks_sql_merge",
                "databricks_sql_merge was explicitly requested and capability evidence supports Delta MERGE.",
            )
        return _fallback_or_unsupported(
            contract,
            fallback_policy,
            requested_engine="databricks_sql_merge",
            fallback_engine="core_managed_scd2_delta_merge" if contract.write.mode == "scd2_historical" else "core_managed_delta",
            blocker="databricks_sql_merge requires SCD1 upsert with Delta MERGE capability.",
        )
    if normalized == "lakeflow_auto_cdc":
        if contract.write.mode in {"scd1_upsert", "scd2_historical"} and capabilities.status("lakeflow_auto_cdc") == "supported":
            return WriteStrategy(
                "native_databricks",
                "lakeflow_auto_cdc",
                "lakeflow_auto_cdc was explicitly requested and capability evidence reports support.",
                warnings=("requires Lakeflow compatibility validation",),
            )
        fallback_engine = "core_managed_scd2_delta_merge" if contract.write.mode == "scd2_historical" else "databricks_sql_merge"
        return _fallback_or_unsupported(
            contract,
            fallback_policy,
            requested_engine="lakeflow_auto_cdc",
            fallback_engine=fallback_engine,
            blocker="lakeflow_auto_cdc requires supported Lakeflow capability evidence and SCD1/SCD2 CDC semantics.",
        )
    return WriteStrategy(
        "unsupported",
        normalized,
        f"Unknown Databricks write engine requested: {requested}",
        blockers=("write_engine",),
    )


def _fallback_or_unsupported(
    contract: SemanticContract,
    fallback_policy: str,
    *,
    requested_engine: str,
    fallback_engine: str,
    blocker: str,
) -> WriteStrategy:
    if fallback_policy in {"fallback_to_core", "preview_only"}:
        return WriteStrategy(
            "contractforge_algorithm",
            fallback_engine,
            f"{requested_engine} was requested, but the adapter selected a ContractForge-compatible fallback.",
            blockers=(blocker,),
            warnings=(f"fallback_policy={fallback_policy}",),
        )
    return WriteStrategy(
        "unsupported",
        requested_engine,
        f"{requested_engine} was requested with fallback_policy=fail, but it cannot be selected safely for {contract.write.mode}.",
        blockers=(blocker,),
    )


def _requested_engine(contract: SemanticContract) -> str | None:
    write_engine = databricks_extensions(contract).get("write_engine")
    if isinstance(write_engine, dict):
        return str(write_engine.get("requested") or write_engine.get("engine") or "").strip() or None
    return str(write_engine).strip() if write_engine else None


def _fallback_policy(contract: SemanticContract) -> str:
    write_engine = databricks_extensions(contract).get("write_engine")
    if isinstance(write_engine, dict):
        return str(write_engine.get("fallback_policy") or "fail")
    return "fail"


def _normalize_engine(value: str) -> str:
    normalized = value.strip().lower().replace("databricks_lakeflow_auto_cdc", "lakeflow_auto_cdc")
    if normalized == "lakeflow":
        return "lakeflow_auto_cdc"
    return normalized
