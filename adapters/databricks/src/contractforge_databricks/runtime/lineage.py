"""Runtime explain and OpenLineage evidence for Databricks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from contractforge_core.diagnostics import ExplainPlanRecord
from contractforge_core.runtime import PreparedInput, QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.diagnostics import render_explain_insert_sql
from contractforge_databricks.execution import SqlRunner
from contractforge_databricks.lineage import render_openlineage_insert_sql
from contractforge_databricks.sql import quote_table_name


def write_runtime_diagnostics(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    prepared: PreparedInput,
    run_id: str,
    target: str,
    status: str,
    started: str,
    finished: str,
    rows_written: int,
    operation_metrics: dict[str, Any],
    catalog: str,
    schema: str,
    query_one: QueryOne | None,
    runtime_metadata: dict[str, Any] | None = None,
) -> dict[str, bool]:
    extensions = databricks_extensions(contract)
    explain = _write_explain(
        runner=runner,
        contract=contract,
        prepared=prepared,
        run_id=run_id,
        target=target,
        extensions=extensions,
        catalog=catalog,
        schema=schema,
        query_one=query_one,
    )
    lineage = _write_openlineage(
        runner=runner,
        contract=contract,
        prepared=prepared,
        run_id=run_id,
        target=target,
        status=status,
        started=started,
        finished=finished,
        rows_written=rows_written,
        operation_metrics=operation_metrics,
        extensions=extensions,
        catalog=catalog,
        schema=schema,
        runtime_metadata=runtime_metadata,
    )
    return {"explain_captured": explain, "openlineage_event_emitted": lineage}


def _write_explain(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    prepared: PreparedInput,
    run_id: str,
    target: str,
    extensions: dict[str, Any],
    catalog: str,
    schema: str,
    query_one: QueryOne | None,
) -> bool:
    if not extensions.get("explain_mode") or query_one is None:
        return False
    explain_format = str(extensions.get("explain_format") or "formatted")
    row = query_one(f"EXPLAIN {explain_format.upper()} SELECT * FROM {quote_table_name(prepared.source_view)}")
    plan_text = _row_value(row, "plan_text") or _row_value(row, "plan") or _row_value(row, "explain")
    if plan_text is None:
        return False
    runner.sql(
        render_explain_insert_sql(
            ExplainPlanRecord(run_id, target, prepared.source_name or prepared.source_view, contract.write.mode, explain_format, str(plan_text)),
            catalog=catalog,
            schema=schema,
        )
    )
    return True


def _write_openlineage(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    prepared: PreparedInput,
    run_id: str,
    target: str,
    status: str,
    started: str,
    finished: str,
    rows_written: int,
    operation_metrics: dict[str, Any],
    extensions: dict[str, Any],
    catalog: str,
    schema: str,
    runtime_metadata: dict[str, Any] | None,
) -> bool:
    if not extensions.get("openlineage_enabled"):
        return False
    operations = contract.operations.metadata if contract.operations and contract.operations.metadata else {}
    runtime = dict(runtime_metadata or {})
    runner.sql(
        render_openlineage_insert_sql(
            contract,
            run_id=run_id,
            source_name=prepared.source_name or prepared.source_view,
            status=status,
            started_at_utc=_parse_ts(started),
            finished_at_utc=_parse_ts(finished),
            rows_read=prepared.rows_read,
            rows_written=rows_written,
            input_schema=_schema_fields(prepared.source_schema),
            output_schema=_schema_fields(prepared.source_schema),
            delta_version_after=_int_or_none(operation_metrics.get("version")),
            operation_metrics=operation_metrics,
            namespace=extensions.get("openlineage_namespace"),
            producer=str(extensions.get("openlineage_producer") or "contractforge-databricks"),
            parent_run_id=operations.get("parent_run_id"),
            spark_version=runtime.get("spark_version"),
            source_code_url=runtime.get("notebook_name"),
            catalog=catalog,
            schema=schema,
        )
    )
    return True


def _schema_fields(schema: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    return tuple((name, dtype) for name, dtype in (schema or {}).items())


def _row_value(row: Any, key: str) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    if hasattr(row, "asDict"):
        return row.asDict().get(key)
    return getattr(row, key, None)


def _parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _int_or_none(value: object) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None
