"""Databricks runtime error payload assembly."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.runtime.utils import today_str, utc_now_str
from contractforge_databricks.security import exception_message, redact_text


def error_log_payload(
    exc: Exception,
    *,
    run_id: str,
    target: str,
    source_table: str | None,
    mode: str,
    runtime_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime = dict(runtime_metadata or {})
    return {
        "run_id": run_id,
        "error_ts_utc": _utc_now(),
        "error_date": _date_now(),
        "occurred_at_utc": _utc_now(),
        "target_table": target,
        "source_table": source_table,
        "mode": mode,
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error_class": _error_class(exc),
        "error_message": exception_message(exc),
        "stack_trace": redact_text(str(exc)),
        "runtime_type": runtime.get("runtime_type"),
        "engine_version": runtime.get("spark_version"),
        "python_version": runtime.get("python_version"),
    }


def _error_class(exc: Exception) -> str:
    getter = getattr(exc, "getErrorClass", None)
    if callable(getter):
        value = getter()
        if value:
            return str(value)
    return type(exc).__name__


def _utc_now() -> str:
    return utc_now_str()


def _date_now() -> str:
    return today_str()
