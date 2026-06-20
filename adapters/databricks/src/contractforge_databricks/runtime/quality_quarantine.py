"""Persist row-level Databricks quality quarantine evidence."""

from __future__ import annotations

from dataclasses import replace
from importlib import import_module
from typing import Any
from uuid import uuid4

from contractforge_core.quality import QualityRuleResult
from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.quality import evaluate_quality
from contractforge_databricks.runtime.models import DatabricksIngestOptions


def apply_declared_quality(
    *,
    spark: Any,
    contract: Any,
    prepared: Any,
    opts: DatabricksIngestOptions,
    run_id: str,
    target: str,
    quality_results: tuple[QualityRuleResult, ...],
) -> tuple[Any, tuple[QualityRuleResult, ...]]:
    if quality_results or not getattr(contract, "quality", ()):
        return prepared, quality_results
    status, evaluated, valid_df, quarantined_df, quarantined_count = evaluate_quality(spark.table(prepared.source_view), contract)
    if status == "NOT_CONFIGURED":
        return prepared, evaluated
    if quarantined_count > 0 and not opts.dry_run:
        persist_quality_quarantine_rows(
            quarantined_df,
            run_id=run_id,
            target_table=target,
            quality_results=evaluated,
            catalog=opts.catalog,
            schema=opts.schema,
        )
    valid_df.createOrReplaceTempView(prepared.source_view)
    return replace(prepared, rows_quarantined=quarantined_count), evaluated


def with_run_id(opts: DatabricksIngestOptions) -> DatabricksIngestOptions:
    return opts if opts.run_id else replace(opts, run_id=f"run-{uuid4()}")


def persist_quality_quarantine_rows(
    quarantined_df: Any,
    *,
    run_id: str,
    target_table: str,
    quality_results: tuple[QualityRuleResult, ...],
    catalog: str,
    schema: str,
) -> None:
    """Append quarantined row payloads to the core quarantine evidence table."""

    failed = tuple(result for result in quality_results if result.failed_count and result.severity == "quarantine")
    if not failed:
        return
    functions = _functions()
    payload_columns = [functions.col(column) for column in getattr(quarantined_df, "columns", ()) or ()]
    reason = _reason(failed)
    quarantine_table = evidence_table_names(catalog, schema)["quarantine"]
    (
        quarantined_df.select(
            functions.lit(run_id).alias("run_id"),
            functions.lit(target_table).alias("target_table"),
            functions.lit(_rule_name(failed)).alias("rule_name"),
            functions.lit(reason).alias("error_reason"),
            functions.to_json(functions.struct(*payload_columns)).alias("record_payload"),
            functions.lit(None).cast("string").alias("record_ref"),
            functions.lit(reason).alias("reason"),
            functions.current_timestamp().alias("quarantined_at_utc"),
        )
        .write.mode("append")
        .insertInto(quarantine_table)
    )


def _rule_name(results: tuple[QualityRuleResult, ...]) -> str:
    return ", ".join(result.rule_name for result in results)


def _reason(results: tuple[QualityRuleResult, ...]) -> str:
    parts = [f"{result.rule_name}: {result.message or 'quality rule failed'}" for result in results]
    return "; ".join(parts)


def _functions() -> Any:
    return import_module("pyspark.sql").functions
