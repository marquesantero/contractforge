"""Platform-neutral write metric normalization."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract


def logical_row_metrics(contract: SemanticContract, rows_written: int) -> dict[str, int]:
    rows = int(rows_written or 0)
    metrics = {
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_deleted": 0,
        "rows_expired": 0,
        "rows_affected": rows,
    }
    if rows <= 0:
        return metrics
    if contract.write.mode in {"scd0_append", "scd0_overwrite", "scd1_hash_diff", "scd2_historical"}:
        metrics["rows_inserted"] = rows
    return metrics


def normalize_rows_written(rows_written: int, row_metrics: dict[str, int]) -> int:
    return max(int(rows_written or 0), int(row_metrics.get("rows_affected") or 0))
