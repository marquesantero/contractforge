"""JSON-friendly GCP cost report planning."""

from __future__ import annotations

from typing import Any

from contractforge_gcp.cost.model import CostModel
from contractforge_gcp.cost.sql import DEFAULT_COST_GROUP_BY, render_operational_cost_query


def build_operational_cost_report(
    *,
    project_id: str | None = None,
    dataset: str = "contractforge_ops",
    lookback_days: int = 30,
    group_by: tuple[str, ...] | None = None,
    cost_model: CostModel | None = None,
    include_failed: bool = True,
    query_only: bool = True,
    runner: Any | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1")
    model = cost_model or CostModel()
    fields = group_by or DEFAULT_COST_GROUP_BY
    query = render_operational_cost_query(
        project_id=project_id,
        dataset=dataset,
        lookback_days=lookback_days,
        group_by=fields,
        cost_model=model,
        include_failed=include_failed,
    )
    rows = [] if query_only or runner is None else _collect_rows(runner.query(f"{query}\nLIMIT {int(limit)}"))
    return {
        "status": "QUERY_ONLY" if query_only or runner is None else "SUCCESS",
        "project_id": project_id,
        "dataset": dataset,
        "lookback_days": lookback_days,
        "group_by": list(fields),
        "include_failed": include_failed,
        "limit": limit,
        "cost_model": {
            "enabled": model.enabled,
            "bytes_processed_per_tib_rate": model.bytes_processed_per_tib_rate,
            "slot_hour_rate": model.slot_hour_rate,
            "currency": model.currency,
        },
        "query": query,
        "rows": rows,
    }


def _collect_rows(result: Any) -> list[dict[str, Any]]:
    rows = getattr(result, "result_rows", None)
    if rows is None and hasattr(result, "collect"):
        rows = result.collect()
    collected = []
    for row in rows or []:
        if hasattr(row, "asDict"):
            collected.append(row.asDict(recursive=True))
        elif isinstance(row, dict):
            collected.append(dict(row))
        else:
            collected.append(dict(row))
    return collected
