"""JSON-friendly cost report planning."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.cost.model import CostModel
from contractforge_databricks.cost.sql import DEFAULT_COST_GROUP_BY, render_operational_cost_query


def build_operational_cost_report(
    *,
    catalog: str = "main",
    schema: str = "ops",
    lookback_days: int = 30,
    group_by: tuple[str, ...] = DEFAULT_COST_GROUP_BY,
    cost_model: CostModel | None = None,
    include_failed: bool = True,
    query_only: bool = True,
    runner: Any | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1")
    model = cost_model or CostModel()
    query = render_operational_cost_query(
        catalog=catalog,
        schema=schema,
        lookback_days=lookback_days,
        group_by=group_by,
        cost_model=model,
        include_failed=include_failed,
    )
    rows = [] if query_only or runner is None else _collect_rows(runner.sql(f"{query}\nLIMIT {int(limit)}"))
    return {
        "status": "QUERY_ONLY" if query_only or runner is None else "SUCCESS",
        "catalog": catalog,
        "schema": schema,
        "lookback_days": lookback_days,
        "group_by": list(group_by),
        "include_failed": include_failed,
        "limit": limit,
        "cost_model": {
            "enabled": model.enabled,
            "dbu_per_hour": model.dbu_per_hour,
            "currency_per_dbu": model.currency_per_dbu,
            "currency": model.currency,
            "hourly_rate": model.hourly_rate,
        },
        "query": query,
        "rows": rows,
    }


def _collect_rows(result: Any) -> list[dict[str, Any]]:
    collected = result.collect() if hasattr(result, "collect") else result
    rows = []
    for row in collected or []:
        if hasattr(row, "asDict"):
            rows.append(row.asDict(recursive=True))
        elif isinstance(row, dict):
            rows.append(dict(row))
        else:
            rows.append(dict(row))
    return rows
