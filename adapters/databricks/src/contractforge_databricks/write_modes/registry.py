"""Databricks runtime registry for adapter-owned custom write modes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from contractforge_core.execution import ExecutionOutcome, canonical_custom_write_mode

DatabricksWriteHandler = Callable[..., ExecutionOutcome]
WRITE_MODE_REGISTRY: dict[str, DatabricksWriteHandler] = {}


def register_write_mode(mode: str, handler: DatabricksWriteHandler, *, overwrite: bool = False) -> str:
    canonical = canonical_custom_write_mode(mode)
    if not callable(handler):
        raise ValueError("write mode handler must be callable")
    if canonical in WRITE_MODE_REGISTRY and not overwrite:
        raise ValueError(f"write mode already registered: {canonical}")
    WRITE_MODE_REGISTRY[canonical] = handler
    return canonical


def unregister_write_mode(mode: str) -> None:
    WRITE_MODE_REGISTRY.pop(canonical_custom_write_mode(mode), None)


def list_write_modes() -> tuple[str, ...]:
    return tuple(sorted(WRITE_MODE_REGISTRY))


def get_write_mode(mode: str) -> DatabricksWriteHandler | None:
    return WRITE_MODE_REGISTRY.get(canonical_custom_write_mode(mode))


def execute_registered_write_mode(mode: str, **kwargs: Any) -> ExecutionOutcome:
    handler = get_write_mode(mode)
    if handler is None:
        raise ValueError(f"Unsupported Databricks write mode: {mode}")
    return handler(**kwargs)


def clear_write_mode_registry() -> None:
    WRITE_MODE_REGISTRY.clear()
