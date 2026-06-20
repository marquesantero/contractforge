"""Shared Snowflake SQL rendering helpers."""

from __future__ import annotations

from typing import Any


def sql_string(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"
