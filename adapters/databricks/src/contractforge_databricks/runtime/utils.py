"""Small Databricks runtime utility helpers without Spark import requirements."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Iterable


def utc_now_ts() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_str() -> str:
    return utc_now_ts().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return utc_now_ts().strftime("%Y-%m-%d")


def new_run_id() -> str:
    return str(uuid.uuid4())


def resolve_run_id(run_id: str | None, run_id_factory: Callable[[], str] | None = None) -> str:
    if run_id:
        return run_id
    if run_id_factory:
        return str(run_id_factory())
    return f"run-{uuid.uuid4()}"


def safe_truncate(text: str | None, max_len: int = 100_000) -> str | None:
    if text is None or len(text) <= max_len:
        return text
    return text[:max_len] + "\n...TRUNCATED..."


def as_list(value: str | Iterable[Any] | None, sep: str = "|") -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(sep) if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def validate_columns(df: Any, columns: Iterable[str], context: str = "columns") -> None:
    available = set(getattr(df, "columns", ()) or ())
    missing = [column for column in columns if column not in available]
    if missing:
        raise ValueError(f"{context} not found: {missing}")
