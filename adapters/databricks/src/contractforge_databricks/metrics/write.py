"""Databricks Delta write metric normalization."""

from __future__ import annotations

from typing import Any

from contractforge_core.metrics import (
    logical_row_metrics as core_logical_row_metrics,
    normalize_rows_written as normalize_rows_written,
)
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.contract_extensions import databricks_extensions


def extract_delta_row_metrics(metrics: dict[str, Any]) -> dict[str, int]:
    operation = metrics.get("operationMetrics") or {}

    def parse(*names: str) -> int:
        for name in names:
            if name in operation and operation[name] is not None:
                try:
                    return int(operation[name])
                except Exception:
                    return 0
        return 0

    return {
        "rows_inserted": parse("numTargetRowsInserted", "numOutputRows"),
        "rows_updated": parse("numTargetRowsUpdated"),
        "rows_deleted": parse("numTargetRowsDeleted"),
        "rows_expired": 0,
    }


def resolve_write_metrics(
    contract: SemanticContract,
    rows_written: int,
    delta_metrics: dict[str, Any],
) -> tuple[dict[str, int], dict[str, Any], str]:
    logical = logical_row_metrics(contract, rows_written)
    operation_metrics = dict(delta_metrics or {})
    operation_metrics["logicalMetrics"] = logical
    if operation_metrics.get("operationMetrics"):
        row_metrics = extract_delta_row_metrics(operation_metrics)
        if contract.write.mode == "scd2_historical":
            row_metrics["rows_expired"] = row_metrics["rows_updated"]
        delta_rows_affected = row_metrics["rows_inserted"] + row_metrics["rows_updated"] + row_metrics["rows_deleted"]
        row_metrics["rows_affected"] = max(logical["rows_affected"], delta_rows_affected)
        operation_metrics["normalizedRowMetrics"] = row_metrics
        return row_metrics, operation_metrics, "mixed"
    operation_metrics["normalizedRowMetrics"] = logical
    return logical, operation_metrics, "logical"


def logical_row_metrics(contract: SemanticContract, rows_written: int) -> dict[str, int]:
    logical = core_logical_row_metrics(contract, rows_written)
    if (
        int(rows_written or 0) > 0
        and contract.write.mode == "scd1_upsert"
        and databricks_extensions(contract).get("merge_strategy") == "replace_partitions"
    ):
        logical["rows_inserted"] = int(rows_written)
    return logical
