"""Runtime input models for Databricks ingestion orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from contractforge_core.runtime import PreparedInput
from contractforge_databricks.runtime.hooks import DatabricksIngestionHooks


PreparedViewInput = PreparedInput


@dataclass(frozen=True)
class DatabricksIngestOptions:
    catalog: str = "main"
    schema: str = "ops"
    dry_run: bool = False
    ensure_table: bool = True
    lock_enabled: bool = False
    lock_owner: str | None = None
    idempotency_key: str | None = None
    idempotency_policy: str = "always_run"
    quality_action: str = "fail"
    run_id: str | None = None
    run_id_factory: Callable[[], str] | None = None
    runtime_metadata: dict[str, Any] | None = None
    target_schema: dict[str, str] | None = None
    allow_review_required: bool = False
    raise_on_failure: bool = True
    hooks: DatabricksIngestionHooks | None = None
