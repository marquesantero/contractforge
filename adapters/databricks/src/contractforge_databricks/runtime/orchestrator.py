"""Databricks runtime orchestration over prepared source views."""
from __future__ import annotations

from typing import Any

from contractforge_core.quality import QualityRuleResult, quality_status
from contractforge_core.runtime import PreparedInput, QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.adapter import DatabricksAdapter
from contractforge_databricks.execution import SqlRunner
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.runtime.hooks import apply_prepared_hook
from contractforge_databricks.runtime.models import DatabricksIngestOptions
from contractforge_databricks.runtime.orchestration_context import (
    RuntimeContext,
    RuntimeProgress,
    build_runtime_context,
    complete_result,
    finalize_dry_run_result,
    finalize_failure_result,
    finalize_skipped_result,
    finalize_success_result,
)
from contractforge_databricks.runtime.write_flow import execute_runtime_write_flow
from contractforge_databricks.state import render_find_idempotent_run_sql


def ingest_databricks_contract(
    contract: dict[str, Any] | SemanticContract,
    *,
    runner: SqlRunner,
    prepared: PreparedInput,
    options: DatabricksIngestOptions | None = None,
    query_one: QueryOne | None = None,
    quality_results: tuple[QualityRuleResult, ...] = (),
) -> dict[str, Any]:
    """Execute one Databricks contract over an already prepared source view."""
    ctx = build_runtime_context(
        contract,
        runner=runner,
        options=options,
        query_one=query_one,
        quality_results=quality_results,
    )
    progress = RuntimeProgress(prepared=prepared)
    raw_quality_status = quality_status(quality_results)

    try:
        _validate_planning(ctx.semantic, ctx.opts)
        progress.prepared = _apply_after_prepare(ctx, progress.prepared)
        skipped = _idempotency_skip(ctx.target, ctx.opts, query_one)
        if skipped:
            return complete_result(
                ctx,
                finalize_skipped_result(
                    ctx,
                    progress,
                    quality_results=quality_results,
                    skipped_by_run_id=skipped.get("run_id"),
                ),
            )
        _raise_for_quality_failure(raw_quality_status, ctx.opts)
        _acquire_lock(ctx)
        progress.prepared = _apply_before_write(ctx, progress.prepared)
        if ctx.opts.dry_run:
            return complete_result(ctx, finalize_dry_run_result(ctx, progress))
        write_flow = execute_runtime_write_flow(
            runner=runner,
            evidence=ctx.evidence,
            contract=ctx.semantic,
            prepared=progress.prepared,
            opts=ctx.opts,
            run_id=ctx.run_id,
            target=ctx.target,
            query_one=query_one,
            quality_results=quality_results,
        )
        progress.schema_changes = write_flow.schema_changes
        progress.governance_results = write_flow.governance_results
        if ctx.opts.hooks and ctx.opts.hooks.after_write:
            ctx.opts.hooks.after_write(ctx.semantic, progress.prepared, write_flow.outcome)
        return complete_result(
            ctx,
            finalize_success_result(
                ctx,
                progress,
                write_flow=write_flow,
                quality_results=quality_results,
                query_one=query_one,
            ),
        )
    except Exception as exc:
        return complete_result(ctx, finalize_failure_result(ctx, progress, exc, quality_results=quality_results))
    finally:
        _release_lock(ctx)


def _apply_after_prepare(ctx: RuntimeContext, prepared: PreparedInput) -> PreparedInput:
    return apply_prepared_hook(ctx.opts.hooks.after_prepare if ctx.opts.hooks else None, ctx.semantic, prepared)


def _apply_before_write(ctx: RuntimeContext, prepared: PreparedInput) -> PreparedInput:
    return apply_prepared_hook(ctx.opts.hooks.before_write if ctx.opts.hooks else None, ctx.semantic, prepared)


def _raise_for_quality_failure(raw_quality_status: str, opts: DatabricksIngestOptions) -> None:
    if raw_quality_status == "FAILED" and opts.quality_action == "fail":
        raise ValueError("Quality gates failed before Databricks write")


def _acquire_lock(ctx: RuntimeContext) -> None:
    if ctx.opts.lock_enabled and not ctx.opts.dry_run:
        ctx.state.acquire_lock(target_table=ctx.target, run_id=ctx.run_id, owner=ctx.opts.lock_owner)


def _release_lock(ctx: RuntimeContext) -> None:
    if ctx.opts.lock_enabled and not ctx.opts.dry_run:
        ctx.state.release_lock(target_table=ctx.target, run_id=ctx.run_id)


def _validate_planning(contract: SemanticContract, opts: DatabricksIngestOptions) -> None:
    runtime = dict(opts.runtime_metadata or {})
    result = DatabricksAdapter.from_evidence(
        target_table=target_full_name(contract),
        runtime_type=str(runtime.get("runtime_type") or "serverless"),
        spark_version=str(runtime["spark_version"]) if runtime.get("spark_version") else None,
    ).plan(contract)
    if result.status == "UNSUPPORTED" or (result.status == "REVIEW_REQUIRED" and not opts.allow_review_required):
        blockers = "; ".join(blocker.message for blocker in result.blockers)
        raise ValueError(f"Databricks planning status {result.status}: {blockers}")


def _idempotency_skip(target: str, opts: DatabricksIngestOptions, query_one: QueryOne | None) -> dict[str, Any] | None:
    if not opts.idempotency_key or opts.idempotency_policy not in {"skip_if_success", "rerun_if_failed", "fail_if_success"}:
        return None
    statement = render_find_idempotent_run_sql(
        target_table=target,
        idempotency_key=opts.idempotency_key,
        status="SUCCESS",
        runs_table=f"{opts.catalog}.{opts.schema}.ctrl_ingestion_runs",
    )
    previous = query_one(statement) if query_one else None
    if not previous:
        return None
    if opts.idempotency_policy == "fail_if_success":
        raise ValueError(f"idempotency_key={opts.idempotency_key!r} already succeeded")
    return previous
