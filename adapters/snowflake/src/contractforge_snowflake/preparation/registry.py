"""Registry primitives for Snowflake preparation SQL steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from contractforge_core.semantic import SemanticContract


@dataclass(frozen=True)
class SnowflakePreparationContext:
    source_sql: str
    contract: SemanticContract


@dataclass(frozen=True)
class SnowflakePreparationStep:
    name: str
    render: Callable[[SnowflakePreparationContext], str]


def apply_preparation_steps(
    contract: SemanticContract,
    source_sql: str,
    steps: tuple[SnowflakePreparationStep, ...],
) -> str:
    context = SnowflakePreparationContext(source_sql=source_sql, contract=contract)
    for step in steps:
        context = SnowflakePreparationContext(source_sql=step.render(context), contract=contract)
    return context.source_sql


__all__ = ["SnowflakePreparationContext", "SnowflakePreparationStep", "apply_preparation_steps"]
