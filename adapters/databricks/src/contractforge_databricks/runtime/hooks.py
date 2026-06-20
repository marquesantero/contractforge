"""Programmatic hooks for Databricks runtime orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from contractforge_core.execution import ExecutionOutcome
from contractforge_core.runtime import PreparedInput
from contractforge_core.semantic import SemanticContract

PreparedHook = Callable[[SemanticContract, PreparedInput], Optional[PreparedInput]]
AfterWriteHook = Callable[[SemanticContract, PreparedInput, Optional[ExecutionOutcome]], None]
AfterFinalizeHook = Callable[[SemanticContract, dict[str, object]], None]


@dataclass(frozen=True)
class DatabricksIngestionHooks:
    """Optional callbacks around the Databricks prepared-view runtime boundary."""

    after_prepare: PreparedHook | None = None
    before_write: PreparedHook | None = None
    after_write: AfterWriteHook | None = None
    after_finalize: AfterFinalizeHook | None = None

    def __post_init__(self) -> None:
        for name in ("after_prepare", "before_write", "after_write", "after_finalize"):
            hook = getattr(self, name)
            if hook is not None and not callable(hook):
                raise ValueError(f"DatabricksIngestionHooks.{name} must be callable")


def apply_prepared_hook(
    hook: PreparedHook | None,
    contract: SemanticContract,
    prepared: PreparedInput,
) -> PreparedInput:
    if hook is None:
        return prepared
    result = hook(contract, prepared)
    if result is None:
        return prepared
    if not isinstance(result, PreparedInput):
        raise ValueError("Databricks prepared hooks must return PreparedInput or None")
    return result
