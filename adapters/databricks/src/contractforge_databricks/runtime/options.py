"""Databricks runtime option resolution from core contract semantics."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.runtime.hooks import DatabricksIngestionHooks
from contractforge_databricks.runtime.models import DatabricksIngestOptions


def effective_ingest_options(contract: SemanticContract, options: DatabricksIngestOptions) -> DatabricksIngestOptions:
    metadata = contract.operations.metadata if contract.operations and contract.operations.metadata else {}
    extensions = databricks_extensions(contract)
    updates: dict[str, Any] = {}
    if options.idempotency_key is None and metadata.get("idempotency_key"):
        updates["idempotency_key"] = str(metadata["idempotency_key"])
    if options.idempotency_policy == "always_run" and metadata.get("idempotency_policy"):
        updates["idempotency_policy"] = str(metadata["idempotency_policy"])
    if options.quality_action == "fail" and metadata.get("on_quality_fail"):
        updates["quality_action"] = str(metadata["on_quality_fail"])
    if options.hooks is None and extensions.get("hooks") is not None:
        hooks = extensions["hooks"]
        if isinstance(hooks, dict):
            hooks = DatabricksIngestionHooks(**hooks)
        if not isinstance(hooks, DatabricksIngestionHooks):
            raise ValueError("extensions.databricks.hooks must be DatabricksIngestionHooks")
        updates["hooks"] = hooks
    if not options.lock_enabled and extensions.get("lock_enabled"):
        updates["lock_enabled"] = True
    return replace(options, **updates) if updates else options
