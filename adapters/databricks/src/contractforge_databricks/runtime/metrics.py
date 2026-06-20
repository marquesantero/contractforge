"""Runtime write metric collection for Databricks."""

from __future__ import annotations

from typing import Any

from contractforge_core.metrics import normalize_rows_written
from contractforge_core.runtime import QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.metrics import (
    latest_operation_metrics_from_history_row,
    render_delta_history_query,
    resolve_write_metrics,
)


def collect_write_metrics(
    *,
    contract: SemanticContract,
    target_table: str,
    rows_written: int,
    query_one: QueryOne | None,
) -> tuple[int, dict[str, Any]]:
    delta_metrics = {}
    if query_one is not None:
        delta_metrics = latest_operation_metrics_from_history_row(
            query_one(render_delta_history_query(target_table=target_table))
        )
    row_metrics, operation_metrics, metrics_source = resolve_write_metrics(contract, rows_written, delta_metrics)
    operation_metrics["metrics_source"] = metrics_source
    normalized = normalize_rows_written(rows_written, row_metrics)
    row_metrics["rows_affected"] = normalized
    operation_metrics["normalizedRowMetrics"] = row_metrics
    return normalized, operation_metrics
