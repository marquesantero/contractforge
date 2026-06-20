"""Shared Snowflake session/connection execution helpers."""

from __future__ import annotations

from typing import Any


def execute(session: Any, command: str) -> None:
    sql = getattr(session, "sql", None)
    if callable(sql):
        result = sql(command)
        if hasattr(result, "collect"):
            result.collect()
        return
    cursor = session.cursor()
    try:
        cursor.execute(command)
    finally:
        if hasattr(cursor, "close"):
            cursor.close()


def collect_rows(session: Any, command: str) -> list[Any]:
    sql = getattr(session, "sql", None)
    if callable(sql):
        return list(sql(command).collect())
    cursor = session.cursor()
    try:
        cursor.execute(command)
        return list(cursor.fetchall()) if getattr(cursor, "description", None) else []
    finally:
        if hasattr(cursor, "close"):
            cursor.close()


def scalar_int(session: Any, command: str, *, key: str) -> int:
    return int(scalar_value(session, command, key=key) or 0)


def scalar_value(session: Any, command: str, *, key: str | None = None) -> Any:
    rows = collect_rows(session, command)
    if not rows:
        return None
    if key is not None:
        value = row_value(rows[0], 0, key)
        if value is not None:
            return value
    row = rows[0]
    if isinstance(row, dict):
        return next(iter(row.values()), None)
    return row_value(row, 0, key or "VALUE")


def row_value(row: Any, index: int, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key) or row.get(key.lower())
    try:
        return row[index]
    except (TypeError, KeyError, IndexError):
        return getattr(row, key, None) or getattr(row, key.lower(), None)
