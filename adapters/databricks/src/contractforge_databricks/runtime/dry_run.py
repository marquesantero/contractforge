"""Dry-run finalization for Databricks runtime ingestion."""

from __future__ import annotations

from typing import Any

from contractforge_core.runtime import PreparedInput
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.evidence import EvidenceWriter
from contractforge_databricks.runtime.finalization import finalize_ingest
from contractforge_databricks.runtime.models import DatabricksIngestOptions
from contractforge_databricks.runtime.schema import preview_schema_changes
from contractforge_databricks.state import StateWriter


def finalize_dry_run(
    *,
    evidence: EvidenceWriter,
    state: StateWriter,
    contract: SemanticContract,
    prepared: PreparedInput,
    opts: DatabricksIngestOptions,
    run_id: str,
    target: str,
    started: str,
    quality_status_value: str,
) -> dict[str, Any]:
    schema_changes = preview_schema_changes(
        contract=contract,
        prepared=prepared,
        target_schema=opts.target_schema,
    )
    return finalize_ingest(
        evidence,
        state,
        contract,
        prepared,
        opts,
        run_id,
        target,
        "DRY_RUN",
        started,
        rows_written=0,
        quality_status_value=quality_status_value,
        schema_changes=schema_changes,
    )
