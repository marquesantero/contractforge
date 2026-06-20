"""Platform-neutral execution window planning helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

_DURATION_RE = re.compile(r"^\s*(\d+)\s*(hour|hours|day|days|week|weeks)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ExecutionWindow:
    start: str
    end: str
    label: str


@dataclass(frozen=True)
class ChildWindowPlan:
    parent_run_id: str
    window: ExecutionWindow
    filter_expression: str
    idempotency_key: str | None
    runtime_parameters: dict[str, str]


def build_time_windows(start: str, end: str, every: str) -> tuple[ExecutionWindow, ...]:
    current = _parse_datetime(start, "execution.window.start")
    final = _parse_datetime(end, "execution.window.end")
    step = _parse_duration(every)
    if current >= final:
        raise ValueError("execution.window.start must be before execution.window.end")
    windows = []
    while current < final:
        next_value = min(current + step, final)
        start_text = _format_datetime(current)
        end_text = _format_datetime(next_value)
        label = f"{start_text.replace(' ', 'T')}__{end_text.replace(' ', 'T')}"
        windows.append(ExecutionWindow(start=start_text, end=end_text, label=label))
        current = next_value
    return tuple(windows)


def combine_filter(existing: str | None, window_filter: str) -> str:
    if existing and existing.strip():
        return f"({existing}) AND {window_filter}"
    return window_filter


def build_child_window_plan(
    *,
    parent_run_id: str,
    column: str,
    window: ExecutionWindow,
    index: int,
    window_filter: str,
    existing_filter: str | None = None,
    base_idempotency_key: str | None = None,
) -> ChildWindowPlan:
    label = window.label or f"window-{index:04d}"
    idempotency_key = f"{base_idempotency_key}:window:{label}" if base_idempotency_key else None
    return ChildWindowPlan(
        parent_run_id=parent_run_id,
        window=window,
        filter_expression=combine_filter(existing_filter, window_filter),
        idempotency_key=idempotency_key,
        runtime_parameters={
            "_contractforge_window_label": label,
            "_contractforge_window_column": column,
            "_contractforge_window_start": window.start,
            "_contractforge_window_end": window.end,
        },
    )


def summarize_window_results(results: tuple[dict[str, object], ...] | list[dict[str, object]]) -> dict[str, int | str]:
    return {
        "status": "FAILED" if any(item.get("status") == "FAILED" for item in results) else "SUCCESS",
        "windows_total": len(results),
        "windows_processed": len(results),
        "windows_succeeded": sum(1 for item in results if item.get("status") in {"SUCCESS", "DRY_RUN", "SKIPPED"}),
        "windows_failed": sum(1 for item in results if item.get("status") == "FAILED"),
        "rows_read": sum(int(item.get("rows_read") or 0) for item in results),
        "rows_written": sum(int(item.get("rows_written") or 0) for item in results),
        "rows_quarantined": sum(int(item.get("rows_quarantined") or 0) for item in results),
    }


def _parse_datetime(value: str, field: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{field} must not be empty")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_duration(value: str) -> timedelta:
    match = _DURATION_RE.match(str(value or ""))
    if not match:
        raise ValueError("execution.window.every must use a value like '1 hour', '1 day' or '1 week'")
    amount = int(match.group(1))
    if amount <= 0:
        raise ValueError("execution.window.every must be positive")
    unit = match.group(2).lower()
    if unit.startswith("hour"):
        return timedelta(hours=amount)
    if unit.startswith("day"):
        return timedelta(days=amount)
    return timedelta(weeks=amount)
