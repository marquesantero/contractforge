"""Shared Databricks evidence SQL rendering helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

from contractforge_databricks.sql import sql_string

TimestampClock = Callable[[], datetime | str]


def cast_sql(value: Any, sql_type: str) -> str:
    if value is None:
        return f"CAST(NULL AS {sql_type})"
    if isinstance(value, datetime):
        text = value.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(value, date):
        text = value.isoformat()
    else:
        text = str(value)
    return f"CAST({sql_string(text)} AS {sql_type})"


def utc_timestamp(clock: TimestampClock | None = None) -> str:
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return str(value)
