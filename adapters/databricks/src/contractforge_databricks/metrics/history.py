"""Delta history metric helpers."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.sql import quote_table_name


def render_delta_history_query(*, target_table: str, limit: int = 1) -> str:
    return f"DESCRIBE HISTORY {quote_table_name(target_table)} LIMIT {int(limit)}"


def latest_operation_metrics_from_history_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "version": row.get("version"),
        "operation": row.get("operation"),
        "operationMetrics": row.get("operationMetrics") or {},
    }
