"""Snowflake write-mode strategy models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from contractforge_core.semantic import SemanticContract


ScalarInt = Callable[[Any, str], int]
WriteSqlRenderer = Callable[["SnowflakeWriteContext"], str]
PrewriteValidator = Callable[["SnowflakeWriteContext"], tuple[str, ...]]
BootstrapRenderer = Callable[[str, str], str]


@dataclass(frozen=True)
class SnowflakeWriteContext:
    contract: SemanticContract
    session: Any
    source_sql: str
    source_columns: tuple[str, ...]
    target: str
    scalar_int: ScalarInt


@dataclass(frozen=True)
class SnowflakeWriteModeStrategy:
    render_sql: WriteSqlRenderer
    bootstrap_sql: BootstrapRenderer | None = None
    prewrite_validator: PrewriteValidator | None = None


__all__ = [
    "BootstrapRenderer",
    "PrewriteValidator",
    "ScalarInt",
    "SnowflakeWriteContext",
    "SnowflakeWriteModeStrategy",
    "WriteSqlRenderer",
]
