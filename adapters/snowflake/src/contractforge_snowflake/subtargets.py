"""Snowflake adapter subtarget registry."""

from __future__ import annotations

from typing import Any, Callable

from contractforge_snowflake.adapter import SnowflakeAdapter
from contractforge_snowflake.capabilities import SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE

_ADAPTER_FACTORIES: dict[str, Callable[..., SnowflakeAdapter]] = {
    SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE: SnowflakeAdapter.sql_warehouse,
}


def adapter_for_subtarget(subtarget: str, *, environment: dict[str, Any] | None = None) -> SnowflakeAdapter:
    try:
        return _ADAPTER_FACTORIES[subtarget](environment=environment)
    except KeyError as exc:
        raise ValueError(f"Unsupported Snowflake adapter subtarget: {subtarget}") from exc


def validate_snowflake_subtarget(subtarget: str) -> None:
    adapter_for_subtarget(subtarget)


def list_snowflake_subtargets() -> tuple[str, ...]:
    return tuple(_ADAPTER_FACTORIES)
