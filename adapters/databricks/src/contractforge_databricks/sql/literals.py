"""Databricks SQL literal helpers."""

from __future__ import annotations

import json
from typing import Any


def sql_string(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(value)
    return sql_string(value)


def sql_int(value: int | None) -> str:
    return "NULL" if value is None else str(int(value))


def sql_json(value: Any) -> str:
    try:
        payload = json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)
    except Exception:
        payload = json.dumps(str(value), ensure_ascii=False)
    return sql_string(payload)
