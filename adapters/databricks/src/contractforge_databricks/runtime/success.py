"""Successful Databricks runtime finalization."""

from __future__ import annotations

from typing import Any

from contractforge_core.execution import ExecutionOutcome
from contractforge_core.quality import QualityRuleResult
from contractforge_core.runtime import PreparedInput, QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.evidence import EvidenceWriter
from contractforge_databricks.runtime.finalization import finalize_ingest
from contractforge_databricks.runtime.lineage import write_runtime_diagnostics
from contractforge_databricks.runtime.metrics import collect_write_metrics
from contractforge_databricks.runtime.models import DatabricksIngestOptions
from contractforge_databricks.runtime.utils import utc_now_str
from contractforge_databricks.runtime.watermark import collect_previous_watermark, collect_watermark_candidate
from contractforge_databricks.state import StateWriter


def finalize_success(
    *,
    evidence: EvidenceWriter,
    state: StateWriter,
    contract: SemanticContract,
    prepared: PreparedInput,
    opts: DatabricksIngestOptions,
    run_id: str,
    target: str,
    started: str,
    outcome: ExecutionOutcome | None,
    logical_rows_written: int,
    quality_status_value: str,
    schema_changes: dict[str, Any],
    governance_results: dict[str, Any],
    query_one: QueryOne | None,
    quality_results: tuple[QualityRuleResult, ...] = (),
    write_started_at: str | None = None,
    write_finished_at: str | None = None,
    stage_durations: dict[str, float] | None = None,
) -> dict[str, Any]:
    rows_written, operation_metrics = collect_write_metrics(
        contract=contract,
        target_table=target,
        rows_written=logical_rows_written,
        query_one=query_one,
    )
    watermark_column, watermark_current = collect_watermark_candidate(
        contract=contract,
        prepared=prepared,
        query_one=query_one,
    )
    _, watermark_previous = collect_previous_watermark(
        contract=contract,
        query_one=query_one,
        catalog=opts.catalog,
        schema=opts.schema,
    )
    source_metadata = prepared.source_metadata or {}
    watermark_previous = source_metadata.get("watermark_previous") or watermark_previous
    diagnostics = write_runtime_diagnostics(
        runner=evidence.runner,
        contract=contract,
        prepared=prepared,
        run_id=run_id,
        target=target,
        status="SUCCESS",
        started=started,
        finished=_utc_now(),
        rows_written=rows_written,
        operation_metrics=operation_metrics,
        catalog=opts.catalog,
        schema=opts.schema,
        query_one=query_one,
        runtime_metadata=opts.runtime_metadata,
    )
    return finalize_ingest(
        evidence,
        state,
        contract,
        prepared,
        opts,
        run_id,
        target,
        "SUCCESS",
        started,
        rows_written=rows_written,
        quality_status_value=quality_status_value,
        quality_results=quality_results,
        operation_metrics=operation_metrics,
        schema_changes=schema_changes,
        governance_results=governance_results,
        write_started_at=write_started_at,
        write_finished_at=write_finished_at,
        stage_durations=stage_durations,
        watermark_column=watermark_column,
        watermark_previous=watermark_previous,
        watermark_current=watermark_current,
        diagnostics=diagnostics,
    )


def _utc_now() -> str:
    return utc_now_str()
