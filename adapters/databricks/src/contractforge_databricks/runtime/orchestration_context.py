"""Private helpers for Databricks runtime orchestration."""

from __future__ import annotations

from typing import Any
from typing import NamedTuple

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.errors import raise_for_failure_result
from contractforge_core.quality import QualityRuleResult, quality_policy_status
from contractforge_core.runtime import PreparedInput, QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.contract_extensions import normalize_databricks_contract
from contractforge_databricks.evidence import EvidenceWriter
from contractforge_databricks.execution import SqlRunner
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.runtime.dry_run import finalize_dry_run
from contractforge_databricks.runtime.errors import error_log_payload
from contractforge_databricks.runtime.finalization import finalize_ingest
from contractforge_databricks.runtime.models import DatabricksIngestOptions
from contractforge_databricks.runtime.options import effective_ingest_options
from contractforge_databricks.runtime.success import finalize_success
from contractforge_databricks.runtime.utils import resolve_run_id, utc_now_str
from contractforge_databricks.runtime.write_flow import WriteFlowResult
from contractforge_databricks.security import exception_message
from contractforge_databricks.state import StateWriter


class RuntimeContext(NamedTuple):
    semantic: SemanticContract
    opts: DatabricksIngestOptions
    target: str
    run_id: str
    started: str
    evidence: EvidenceWriter
    state: StateWriter
    quality_status_value: str


class RuntimeProgress:
    __slots__ = ("prepared", "schema_changes", "governance_results")

    def __init__(self, prepared: PreparedInput) -> None:
        self.prepared = prepared
        self.schema_changes: dict[str, Any] = {}
        self.governance_results: dict[str, Any] = {}


def build_runtime_context(
    contract: dict[str, Any] | SemanticContract,
    *,
    runner: SqlRunner,
    options: DatabricksIngestOptions | None,
    query_one: QueryOne | None,
    quality_results: tuple[QualityRuleResult, ...],
) -> RuntimeContext:
    base_opts = options or DatabricksIngestOptions()
    semantic = contract if isinstance(contract, SemanticContract) else semantic_contract_from_mapping(normalize_databricks_contract(contract))
    opts = effective_ingest_options(semantic, base_opts)
    target = target_full_name(semantic)
    return RuntimeContext(
        semantic=semantic,
        opts=opts,
        target=target,
        run_id=resolve_run_id(opts.run_id, opts.run_id_factory),
        started=utc_now_str(),
        evidence=EvidenceWriter(runner, catalog=opts.catalog, schema=opts.schema),
        state=StateWriter(runner, catalog=opts.catalog, schema=opts.schema, query_one=query_one),
        quality_status_value=quality_policy_status(quality_results, on_quality_fail=opts.quality_action),
    )


def complete_result(ctx: RuntimeContext, result: dict[str, Any]) -> dict[str, Any]:
    if ctx.opts.hooks and ctx.opts.hooks.after_finalize:
        ctx.opts.hooks.after_finalize(ctx.semantic, result)
    if ctx.opts.raise_on_failure:
        raise_for_failure_result(result)
    return result


def finalize_skipped_result(
    ctx: RuntimeContext,
    progress: RuntimeProgress,
    *,
    quality_results: tuple[QualityRuleResult, ...],
    skipped_by_run_id: object,
) -> dict[str, Any]:
    return finalize_ingest(
        ctx.evidence,
        ctx.state,
        ctx.semantic,
        progress.prepared,
        ctx.opts,
        ctx.run_id,
        ctx.target,
        "SKIPPED",
        ctx.started,
        rows_written=0,
        quality_status_value="SKIPPED",
        quality_results=quality_results,
        skip_reason="idempotency_key_already_succeeded",
        skipped_by_run_id=str(skipped_by_run_id) if skipped_by_run_id else None,
    )


def finalize_dry_run_result(ctx: RuntimeContext, progress: RuntimeProgress) -> dict[str, Any]:
    return finalize_dry_run(
        evidence=ctx.evidence,
        state=ctx.state,
        contract=ctx.semantic,
        prepared=progress.prepared,
        opts=ctx.opts,
        run_id=ctx.run_id,
        target=ctx.target,
        started=ctx.started,
        quality_status_value=ctx.quality_status_value,
    )


def finalize_success_result(
    ctx: RuntimeContext,
    progress: RuntimeProgress,
    *,
    write_flow: WriteFlowResult,
    quality_results: tuple[QualityRuleResult, ...],
    query_one: QueryOne | None,
) -> dict[str, Any]:
    return finalize_success(
        evidence=ctx.evidence,
        state=ctx.state,
        contract=ctx.semantic,
        prepared=progress.prepared,
        opts=ctx.opts,
        run_id=ctx.run_id,
        target=ctx.target,
        started=ctx.started,
        outcome=write_flow.outcome,
        logical_rows_written=write_flow.logical_rows_written,
        quality_status_value=ctx.quality_status_value,
        quality_results=quality_results,
        schema_changes=progress.schema_changes,
        governance_results=progress.governance_results,
        write_started_at=write_flow.write_started_at,
        write_finished_at=write_flow.write_finished_at,
        stage_durations=write_flow.stage_durations,
        query_one=query_one,
    )


def finalize_failure_result(
    ctx: RuntimeContext,
    progress: RuntimeProgress,
    exc: Exception,
    *,
    quality_results: tuple[QualityRuleResult, ...],
) -> dict[str, Any]:
    error_message = exception_message(exc)
    if not ctx.opts.dry_run:
        ctx.evidence.write_error_log(
            error_log_payload(
                exc,
                run_id=ctx.run_id,
                target=ctx.target,
                source_table=progress.prepared.source_name or progress.prepared.source_view,
                mode=ctx.semantic.write.mode,
                runtime_metadata=ctx.opts.runtime_metadata,
            )
        )
    return finalize_ingest(
        ctx.evidence,
        ctx.state,
        ctx.semantic,
        progress.prepared,
        ctx.opts,
        ctx.run_id,
        ctx.target,
        "FAILED",
        ctx.started,
        rows_written=0,
        quality_status_value=ctx.quality_status_value,
        quality_results=quality_results,
        error_message=error_message,
        schema_changes=progress.schema_changes,
        governance_results=progress.governance_results,
    )
