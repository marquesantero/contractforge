"""Databricks runtime orchestration for execution windows."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.execution import ExecutionWindow, build_time_windows, summarize_window_results
from contractforge_core.quality import QualityRuleResult
from contractforge_core.runtime import QueryOne
from contractforge_core.watermark import extract_watermark_field_value
from contractforge_databricks.execution import build_child_window_plan
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.runtime.models import DatabricksIngestOptions
from contractforge_databricks.runtime.orchestrator import ingest_databricks_contract
from contractforge_databricks.runtime.sources import prepare_contract_source_view
from contractforge_databricks.state.queries import render_select_previous_watermark_sql


def has_windowed_execution(contract_mapping: dict[str, Any]) -> bool:
    execution = contract_mapping.get("execution")
    if not isinstance(execution, dict):
        return False
    catchup = execution.get("catchup")
    return isinstance(execution.get("window"), dict) or (isinstance(catchup, dict) and bool(catchup.get("enabled")))


def ingest_windowed_databricks_contract(
    contract_mapping: dict[str, Any],
    *,
    spark: Any,
    runner: Any,
    options: DatabricksIngestOptions,
    query_one: QueryOne | None = None,
    quality_results: tuple[QualityRuleResult, ...] = (),
    view_name: str | None = None,
    collect_metrics: bool = False,
) -> dict[str, Any]:
    window_config = _window_config(contract_mapping, options=options, query_one=query_one)
    windows = _windows(window_config)
    parent_run_id = options.run_id or f"run-{uuid4()}"
    results: list[dict[str, Any]] = []
    for index, window in enumerate(windows, start=1):
        child_plan = build_child_window_plan(
            parent_run_id=parent_run_id,
            column=str(window_config["column"]),
            window=window,
            index=index,
            existing_filter=contract_mapping.get("filter_expression"),
            base_idempotency_key=contract_mapping.get("idempotency_key"),
        )
        child_mapping = _child_contract_mapping(contract_mapping, child_plan)
        child_contract = semantic_contract_from_mapping(child_mapping)
        child_opts = replace(
            options,
            run_id=f"{parent_run_id}:window:{index:04d}",
            idempotency_key=child_plan.idempotency_key or options.idempotency_key,
        )
        prepared = prepare_contract_source_view(
            spark,
            child_contract,
            view_name=_child_view_name(child_contract, view_name, index),
            collect_metrics=collect_metrics,
            query_one=query_one,
            evidence_catalog=child_opts.catalog,
            evidence_schema=child_opts.schema,
        )
        result = ingest_databricks_contract(
            child_contract,
            runner=runner,
            prepared=prepared,
            options=child_opts,
            query_one=query_one,
            quality_results=quality_results,
        )
        result["execution_window"] = _window_payload(child_plan.window, str(window_config["column"]))
        results.append(result)
        if result.get("status") == "FAILED" and window_config.get("stop_on_failure", True):
            break
    return _summary(parent_run_id, windows, results)


def _window_config(
    contract_mapping: dict[str, Any],
    *,
    options: DatabricksIngestOptions,
    query_one: QueryOne | None,
) -> dict[str, Any]:
    execution = dict(contract_mapping.get("execution") or {})
    if isinstance(execution.get("window"), dict):
        return dict(execution["window"])
    catchup = dict(execution.get("catchup") or {})
    if not catchup.get("enabled"):
        raise ValueError("windowed execution requires execution.window or enabled execution.catchup")
    start = catchup.get("start") or _previous_watermark_start(contract_mapping, options, query_one, catchup)
    return {
        "column": catchup.get("column") or _single_watermark_column(contract_mapping),
        "start": start,
        "end": catchup.get("end"),
        "every": catchup.get("every"),
        "stop_on_failure": catchup.get("stop_on_failure", True),
    }


def _windows(config: dict[str, Any]) -> tuple[ExecutionWindow, ...]:
    explicit = config.get("windows")
    if explicit:
        return tuple(
            ExecutionWindow(start=str(item["start"]), end=str(item["end"]), label=str(item.get("label") or ""))
            for item in explicit
        )
    missing = [key for key in ("column", "start", "end", "every") if not config.get(key)]
    if missing:
        raise ValueError(f"execution window requires: {', '.join(missing)}")
    return build_time_windows(str(config["start"]), str(config["end"]), str(config["every"]))


def _child_contract_mapping(contract_mapping: dict[str, Any], child_plan: Any) -> dict[str, Any]:
    child = dict(contract_mapping)
    child["filter_expression"] = child_plan.filter_expression
    child["parent_run_id"] = child_plan.parent_run_id
    if child_plan.idempotency_key:
        child["idempotency_key"] = child_plan.idempotency_key
    runtime = dict(child.get("runtime_parameters") or {})
    runtime.update(child_plan.runtime_parameters)
    child["runtime_parameters"] = runtime
    child.pop("execution", None)
    return child


def _summary(parent_run_id: str, windows: tuple[ExecutionWindow, ...], results: list[dict[str, Any]]) -> dict[str, Any]:
    summary = dict(summarize_window_results(results))
    summary.update(
        {
            "run_id": parent_run_id,
            "parent_run_id": parent_run_id,
            "windows_total": len(windows),
            "windows_processed": len(results),
            "window_results": results,
        }
    )
    return summary


def _previous_watermark_start(
    contract_mapping: dict[str, Any],
    options: DatabricksIngestOptions,
    query_one: QueryOne | None,
    catchup: dict[str, Any],
) -> str:
    if query_one is None:
        raise ValueError("execution.catchup.start is required when query_one is not provided")
    contract = semantic_contract_from_mapping(contract_mapping)
    row = query_one(
        render_select_previous_watermark_sql(
            target_table=target_full_name(contract),
            state_table=f"{options.catalog}.{options.schema}.ctrl_ingestion_state",
        )
    )
    raw = row.get("watermark_value") if isinstance(row, dict) else None
    start = extract_watermark_field_value(raw, catchup.get("column") or _single_watermark_column(contract_mapping))
    if not start:
        raise ValueError("execution.catchup.start is required when no previous watermark exists")
    return start


def _single_watermark_column(contract_mapping: dict[str, Any]) -> str:
    value = contract_mapping.get("watermark_columns")
    columns = [value] if isinstance(value, str) else list(value or ())
    columns = [str(item).strip() for item in columns if str(item).strip()]
    if len(columns) != 1:
        raise ValueError("execution.catchup.column is required unless exactly one watermark column is configured")
    return columns[0]


def _child_view_name(contract: Any, view_name: str | None, index: int) -> str:
    base = view_name or f"cf_source_{target_full_name(contract).replace('`', '').replace('.', '_')}"
    return f"{base}_{index:04d}"


def _window_payload(window: ExecutionWindow, column: str) -> dict[str, str]:
    return {"label": window.label, "column": column, "start": window.start, "end": window.end}
