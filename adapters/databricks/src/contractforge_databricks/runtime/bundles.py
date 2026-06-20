"""Databricks execution helpers for core contract bundles."""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from contractforge_core.contracts import load_contract_bundle, semantic_contract_from_mapping
from contractforge_core.quality import QualityRuleResult
from contractforge_core.runtime import PreparedInput, QueryOne

from contractforge_databricks.contract_extensions import normalize_databricks_contract
from contractforge_databricks.annotations import apply_annotations_contract
from contractforge_databricks.evidence import EvidenceWriter
from contractforge_databricks.execution import SqlRunner
from contractforge_databricks.governance import apply_access_contract, apply_governance_contract
from contractforge_databricks.preparation import apply_contract_preparation, apply_write_staging
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.runtime.available_now import run_available_now_stream
from contractforge_databricks.runtime.cache import cache_prepared_source_if_requested, uncache_prepared_source_if_needed
from contractforge_databricks.runtime.control_tables import ensure_control_tables
from contractforge_databricks.runtime.models import DatabricksIngestOptions
from contractforge_databricks.runtime.options import effective_ingest_options
from contractforge_databricks.runtime.orchestrator import ingest_databricks_contract
from contractforge_databricks.runtime.quality_quarantine import apply_declared_quality, with_run_id
from contractforge_databricks.runtime.spark_defaults import spark_query_one, with_spark_runtime_defaults
from contractforge_databricks.runtime.source_metadata import schema_types
from contractforge_databricks.runtime.sources import prepare_contract_source_view
from contractforge_databricks.runtime.windows import has_windowed_execution, ingest_windowed_databricks_contract


def ingest_databricks_bundle(
    path: str | Path,
    *,
    spark: Any,
    runner: SqlRunner,
    options: DatabricksIngestOptions | None = None,
    query_one: QueryOne | None = None,
    quality_results: tuple[QualityRuleResult, ...] = (),
    view_name: str | None = None,
    collect_metrics: bool = False,
) -> dict[str, Any]:
    bundle = load_contract_bundle(path)
    contract_mapping = normalize_databricks_contract(bundle.contract)
    contract = semantic_contract_from_mapping(contract_mapping)
    opts = effective_ingest_options(contract, options or DatabricksIngestOptions())
    target = target_full_name(contract)
    opts = with_spark_runtime_defaults(spark, opts, target)
    opts = with_run_id(opts)
    effective_query_one = query_one or spark_query_one(spark)
    if not opts.dry_run:
        ensure_control_tables(runner=runner, catalog=opts.catalog, schema=opts.schema)
    if has_windowed_execution(contract_mapping):
        return ingest_windowed_databricks_contract(
            contract_mapping,
            spark=spark,
            runner=runner,
            options=opts,
            query_one=effective_query_one,
            quality_results=quality_results,
            view_name=view_name,
            collect_metrics=collect_metrics,
        )
    if _is_available_now_contract(contract):
        return _ingest_available_now_bundle(
            contract_mapping,
            contract,
            spark=spark,
            runner=runner,
            opts=opts,
            query_one=effective_query_one,
            quality_results=quality_results,
            collect_metrics=collect_metrics,
        )
    prepared = prepare_contract_source_view(
        spark,
        contract,
        view_name=view_name or _view_name(contract),
        collect_metrics=collect_metrics,
        query_one=effective_query_one,
        evidence_catalog=opts.catalog,
        evidence_schema=opts.schema,
    )
    cached = cache_prepared_source_if_requested(spark, contract, prepared)
    try:
        prepared, quality_results = apply_declared_quality(
            spark=spark,
            contract=contract,
            prepared=prepared,
            opts=opts,
            run_id=opts.run_id or "",
            target=target,
            quality_results=quality_results,
        )
        return ingest_databricks_contract(
            contract,
            runner=runner,
            prepared=prepared,
            options=opts,
            query_one=effective_query_one,
            quality_results=quality_results,
        )
    finally:
        uncache_prepared_source_if_needed(spark, prepared, cached)


def _view_name(contract: Any) -> str:
    target = target_full_name(contract).replace("`", "").replace(".", "_")
    return f"cf_source_{target}"


def _ingest_available_now_bundle(
    contract_mapping: dict[str, Any],
    contract: Any,
    *,
    spark: Any,
    runner: SqlRunner,
    opts: DatabricksIngestOptions,
    query_one: QueryOne | None,
    quality_results: tuple[QualityRuleResult, ...],
    collect_metrics: bool,
) -> dict[str, Any]:
    stream_run_id = opts.run_id or f"stream-{uuid4()}"
    evidence = None if opts.dry_run else EvidenceWriter(runner, catalog=opts.catalog, schema=opts.schema)

    def ingest_batch(prepared: PreparedInput, batch_id: int) -> dict[str, Any]:
        child_mapping = dict(contract_mapping)
        child_mapping["parent_run_id"] = stream_run_id
        if opts.idempotency_key:
            child_mapping["idempotency_key"] = f"{opts.idempotency_key}:batch:{batch_id}"
        child_contract = semantic_contract_from_mapping(child_mapping)
        prepared_batch = _prepare_available_now_batch(spark, child_contract, prepared, collect_metrics=collect_metrics)
        cached = cache_prepared_source_if_requested(spark, child_contract, prepared_batch)
        try:
            child_opts = replace(opts, run_id=f"{stream_run_id}:batch:{batch_id}", raise_on_failure=False)
            prepared_batch, batch_quality = apply_declared_quality(
                spark=spark,
                contract=child_contract,
                prepared=prepared_batch,
                opts=child_opts,
                run_id=child_opts.run_id or "",
                target=target_full_name(child_contract),
                quality_results=quality_results,
            )
            return ingest_databricks_contract(
                child_contract,
                runner=runner,
                prepared=prepared_batch,
                options=child_opts,
                query_one=query_one,
                quality_results=batch_quality,
            )
        finally:
            uncache_prepared_source_if_needed(spark, prepared_batch, cached)

    return run_available_now_stream(
        spark,
        contract,
        stream_run_id=stream_run_id,
        batch_ingestor=ingest_batch,
        evidence=evidence,
        query_one=query_one,
        runtime_metadata=opts.runtime_metadata,
    )


def _prepare_available_now_batch(
    spark: Any,
    contract: Any,
    prepared: PreparedInput,
    *,
    collect_metrics: bool,
) -> PreparedInput:
    df = spark.table(prepared.source_view)
    df = apply_contract_preparation(df, contract)
    df = apply_write_staging(df, contract)
    prepared_view = f"{prepared.source_view}_prepared"
    df.createOrReplaceTempView(prepared_view)
    return replace(
        prepared,
        source_view=prepared_view,
        source_columns=tuple(str(column) for column in getattr(df, "columns", ()) or ()),
        source_schema=schema_types(df),
        rows_read=int(df.count()) if collect_metrics else prepared.rows_read,
    )


def _is_available_now_contract(contract: Any) -> bool:
    source = contract.source.raw or {}
    return bool(
        (contract.operations and contract.operations.available_now_streaming)
        or source.get("trigger") == "available_now"
        or str(source.get("type") or "").endswith("_available_now")
    )


def apply_databricks_governance_bundle(path: str | Path, *, runner: SqlRunner) -> dict[str, Any]:
    return apply_governance_contract(runner=runner, contract=_bundle_contract(path))


def apply_databricks_annotations_bundle(path: str | Path, *, runner: SqlRunner) -> dict[str, Any]:
    return asdict(apply_annotations_contract(runner=runner, contract=_bundle_contract(path)))


def apply_databricks_access_bundle(path: str | Path, *, runner: SqlRunner) -> dict[str, Any]:
    return asdict(apply_access_contract(runner=runner, contract=_bundle_contract(path)))


def _bundle_contract(path: str | Path) -> Any:
    bundle = load_contract_bundle(path)
    return semantic_contract_from_mapping(normalize_databricks_contract(bundle.contract))
