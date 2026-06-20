"""Platform-neutral partition predicate inputs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def distinct_partition_values(values: Iterable[Any], *, max_values: int = 1000) -> tuple[Any, ...]:
    distinct_values = tuple(dict.fromkeys(values))
    if not distinct_values:
        raise ValueError("partition predicate requires at least one value")
    if len(distinct_values) > max_values:
        raise ValueError(f"partition predicate has {len(distinct_values)} values, above limit {max_values}")
    return distinct_values
