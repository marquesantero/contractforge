"""Render non-executing SQL notes for Databricks write modes."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.rendering.names import target_full_name


def render_write_mode_sql_notes(contract: SemanticContract) -> str:
    target = target_full_name(contract)
    mode = contract.write.mode
    lines = [
        "-- Databricks write mode review notes.",
        "-- This artifact is not an executable job script.",
        f"-- Target: {target}",
        f"-- Mode: {mode}",
        "",
    ]
    if mode == "scd0_append":
        lines.append("-- Expected implementation: Delta append with schema policy applied by adapter.")
    elif mode == "scd0_overwrite":
        lines.append("-- Expected implementation: Delta overwrite or scoped replaceWhere when declared.")
    elif mode == "scd1_upsert":
        lines.append("-- Expected implementation: SCD1 Delta MERGE current-state upsert by merge keys.")
    elif mode == "scd1_hash_diff":
        lines.append("-- Expected implementation: SCD1 hash current source rows and append changed versions.")
    elif mode == "scd2_historical":
        lines.append("-- Expected implementation: Delta MERGE with valid_from, valid_to, is_current, row_hash.")
    elif mode == "snapshot_soft_delete":
        lines.append("-- Expected implementation: Delta MERGE with NOT MATCHED BY SOURCE soft-delete update.")
    else:
        lines.append("-- Unsupported write mode.")
    return "\n".join(lines) + "\n"
