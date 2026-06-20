"""Databricks execution window SQL helpers."""

from __future__ import annotations

import re

from contractforge_core.execution import (
    ChildWindowPlan,
    ExecutionWindow,
    build_time_windows,
    combine_filter,
    summarize_window_results,
)
from contractforge_core.execution import build_child_window_plan as build_core_child_window_plan
from contractforge_databricks.sql import quote_identifier, sql_string

_SIMPLE_COLUMN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def render_window_filter_sql(column: str, window: ExecutionWindow) -> str:
    if not _SIMPLE_COLUMN_RE.match(column):
        raise ValueError("execution window column must be a simple column name")
    quoted = quote_identifier(column)
    return (
        f"(CAST({quoted} AS TIMESTAMP) >= CAST({sql_string(window.start)} AS TIMESTAMP) "
        f"AND CAST({quoted} AS TIMESTAMP) < CAST({sql_string(window.end)} AS TIMESTAMP))"
    )


def build_child_window_plan(
    *,
    parent_run_id: str,
    column: str,
    window: ExecutionWindow,
    index: int,
    existing_filter: str | None = None,
    base_idempotency_key: str | None = None,
) -> ChildWindowPlan:
    return build_core_child_window_plan(
        parent_run_id=parent_run_id,
        column=column,
        window=window,
        index=index,
        window_filter=render_window_filter_sql(column, window),
        existing_filter=existing_filter,
        base_idempotency_key=base_idempotency_key,
    )


__all__ = [
    "ChildWindowPlan",
    "ExecutionWindow",
    "build_child_window_plan",
    "build_time_windows",
    "combine_filter",
    "render_window_filter_sql",
    "summarize_window_results",
]
