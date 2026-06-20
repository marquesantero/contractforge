"""Snowflake source renderer models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SnowflakeSourcePlan:
    sql: str
    metadata: dict[str, Any]
    commands: tuple[str, ...] = ()


__all__ = ["SnowflakeSourcePlan"]
