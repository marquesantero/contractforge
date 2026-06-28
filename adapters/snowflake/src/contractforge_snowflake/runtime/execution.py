"""Snowflake library-runner execution strategies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.security.redaction import redact_text
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.access import apply_snowflake_access
from contractforge_snowflake.annotations import apply_snowflake_annotations
from contractforge_snowflake.contract_extensions import snowflake_extensions
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence import record_explain_evidence, record_lineage_evidence, record_schema_change_evidence
from contractforge_snowflake.operations import record_snowflake_operations
from contractforge_snowflake.preparation import apply_preparation_sql
from contractforge_snowflake.naming import snowflake_target_name
from contractforge_snowflake.runtime.quality import apply_quality_rules
from contractforge_snowflake.runtime.schema_policy import enforce_schema_policy
from contractforge_snowflake.session_ops import scalar_value
from contractforge_snowflake.sources import render_snowflake_source
from contractforge_snowflake.sources.registry import snowflake_source_type
from contractforge_snowflake.sources.rest_api import materialize_rest_api_source
from contractforge_snowflake.sources.table_refs import contract_with_snowflake_source_refs
from contractforge_snowflake.state import apply_snowflake_state_filter, record_snowflake_state
from contractforge_snowflake.sql import sql_string
from contractforge_snowflake.values import string_or_none as _string_or_none
from contractforge_snowflake.write_modes import prewrite_validation_commands, render_write_sql, target_bootstrap_commands
from contractforge_snowflake.write_modes.hash_diff import hash_diff_candidate_count_sql
from contractforge_snowflake.write_modes.models import SnowflakeWriteContext


@dataclass(frozen=True)
class SnowflakeExecutionResult:
    status: str
    target: str
    write_mode: str
    commands: tuple[str, ...]
    metrics: dict[str, Any]


@dataclass(frozen=True)
class SnowflakeStatementResult:
    command: str
    query_id: str | None = None
    rowcount: int | None = None


@dataclass(frozen=True)
class SnowflakeRuntimeEvidenceCapture:
    commands: tuple[str, ...]
    metrics: dict[str, Any]


@dataclass(frozen=True)
class SnowflakePostWriteEffects:
    annotation_commands: tuple[str, ...] = ()
    access_commands: tuple[str, ...] = ()
    operations_commands: tuple[str, ...] = ()


@dataclass(frozen=True)
class SnowflakeRuntimeEvidenceResult:
    lineage_commands: tuple[str, ...] = ()
    state_commands: tuple[str, ...] = ()
    metrics: dict[str, Any] | None = None


def execute_snowflake_contract(
    contract: dict[str, Any],
    *,
    session: Any,
    environment: SnowflakeEnvironment | dict[str, Any] | None = None,
    run_id: str | None = None,
    set_query_tag: bool = True,
) -> SnowflakeExecutionResult:
    """Execute supported Snowflake runtime modes through a stable session API."""

    if session is None:
        raise ValueError("Snowflake runtime execution requires a Snowflake session")
    semantic = contract_with_snowflake_source_refs(semantic_contract_from_mapping(contract))
    source_plan = _source_plan(semantic, session=session, run_id=run_id)
    source_sql = source_plan.sql
    source_sql = apply_preparation_sql(semantic, source_sql)
    target = snowflake_target_name(semantic)
    query_tag = _query_tag_sql(semantic, run_id=run_id, target=target)
    statement_results: list[SnowflakeStatementResult] = []
    if set_query_tag:
        statement_results.append(_execute(session, query_tag))
    context_command = _snowflake_context_sql()
    snowflake_context = _snowflake_context(session, context_command)
    env = environment if isinstance(environment, SnowflakeEnvironment) else SnowflakeEnvironment.from_contract(environment)
    source_materialization_commands: tuple[str, ...] = ()
    for command in source_plan.commands:
        statement_results.append(_execute(session, command))
        source_materialization_commands = (*source_materialization_commands, command)
    state_filter_commands: tuple[str, ...] = ()
    if run_id:
        state_filter = apply_snowflake_state_filter(session=session, environment=env, contract=semantic, source_sql=source_sql)
        source_sql = state_filter.source_sql
        state_filter_commands = state_filter.commands
    bootstrap_commands = target_bootstrap_commands(semantic, source_sql=source_sql, target=target)
    for command in bootstrap_commands:
        statement_results.append(_execute(session, command))
    schema_policy = enforce_schema_policy(session=session, contract=semantic, source_sql=source_sql, target=target)
    schema_change_commands: tuple[str, ...] = ()
    if run_id and schema_policy.schema_changes:
        schema_evidence = record_schema_change_evidence(
            session,
            environment=env,
            contract=semantic,
            run_id=run_id,
            schema_changes=schema_policy.schema_changes,
        )
        schema_change_commands = schema_evidence.commands
    prequality_write_context = SnowflakeWriteContext(
        contract=semantic,
        session=session,
        source_sql=source_sql,
        source_columns=schema_policy.source_columns,
        target=target,
        scalar_int=_scalar_int,
    )
    validation_commands = prewrite_validation_commands(prequality_write_context)
    rows_read_sql = _count_sql(source_sql)
    rows_read = _scalar_int(session, rows_read_sql)
    quality_commands: tuple[str, ...] = ()
    quality_status = "NOT_CONFIGURED"
    quality_results: tuple[dict[str, Any], ...] = ()
    if semantic.quality:
        if not run_id:
            raise ValueError("Snowflake quality execution requires run_id")
        quality = apply_quality_rules(session=session, environment=env, contract=semantic, run_id=run_id, source_sql=source_sql)
        source_sql = quality.source_sql
        quality_commands = quality.commands
        quality_status = quality.status
        quality_results = quality.results
    rows_to_write = _scalar_int(session, _count_sql(source_sql)) if quality_status == "QUARANTINED" else rows_read
    write_context = SnowflakeWriteContext(
        contract=semantic,
        session=session,
        source_sql=source_sql,
        source_columns=schema_policy.source_columns,
        target=target,
        scalar_int=_scalar_int,
    )
    candidate_count_sql: str | None = None
    hash_diff_candidate_rows: int | None = None
    if semantic.write.mode == "scd1_hash_diff":
        candidate_count_sql = hash_diff_candidate_count_sql(write_context)
        hash_diff_candidate_rows = _scalar_int(session, candidate_count_sql)
    write_sql = render_write_sql(write_context)
    write_started_at = _utc_now()
    write_result = _execute(session, write_sql)
    write_finished_at = _utc_now()
    statement_results.append(write_result)
    explain_capture = SnowflakeRuntimeEvidenceCapture(commands=(), metrics={})
    if run_id and _explain_enabled(semantic):
        explain_capture = _capture_explain(
            session=session,
            environment=env,
            contract=semantic,
            run_id=run_id,
            statement=write_sql,
        )
    post_write = _apply_post_write_effects(session=session, environment=env, contract=semantic, run_id=run_id)
    runtime_evidence = _record_runtime_evidence(
        session=session,
        environment=env,
        contract=semantic,
        run_id=run_id,
        rows_read=rows_read,
        rows_to_write=rows_to_write,
        write_result=write_result,
        statement_results=tuple(statement_results),
        snowflake_context=snowflake_context,
        write_started_at=write_started_at,
        write_finished_at=write_finished_at,
        source_metadata=source_plan.metadata,
        schema_changes=schema_policy.schema_changes,
        quality_status=quality_status,
        quality_results=quality_results,
        explain_metrics=explain_capture.metrics,
        extra_metrics=(
            {"hash_diff_candidate_rows": hash_diff_candidate_rows}
            if hash_diff_candidate_rows is not None
            else {}
        ),
        source_sql=source_sql,
    )
    commands = (
        query_tag,
        context_command,
        *source_materialization_commands,
        *state_filter_commands,
        *bootstrap_commands,
        *schema_policy.commands,
        *schema_change_commands,
        *validation_commands,
        rows_read_sql,
        *quality_commands,
        *((candidate_count_sql,) if candidate_count_sql else ()),
        write_sql,
        *explain_capture.commands,
        *post_write.annotation_commands,
        *post_write.access_commands,
        *post_write.operations_commands,
        *runtime_evidence.lineage_commands,
        *runtime_evidence.state_commands,
    )
    metrics = _runtime_metrics(
        contract=semantic,
        rows_read=rows_read,
        rows_to_write=rows_to_write,
        write_result=write_result,
        statement_results=tuple(statement_results),
        snowflake_context=snowflake_context,
        command_count=len(commands),
        write_started_at=write_started_at,
        write_finished_at=write_finished_at,
        source_metadata=source_plan.metadata,
        schema_changes=schema_policy.schema_changes,
        quality_status=quality_status,
        quality_results=quality_results,
        extra_metrics={
            **explain_capture.metrics,
            **(
                {"hash_diff_candidate_rows": hash_diff_candidate_rows}
                if hash_diff_candidate_rows is not None
                else {}
            ),
            **({"lineage_status": "RECORDED"} if runtime_evidence.lineage_commands else {}),
        },
    )
    return SnowflakeExecutionResult(
        status="SUCCESS",
        target=target,
        write_mode=semantic.write.mode,
        commands=commands,
        metrics=metrics,
    )


def _source_plan(semantic: SemanticContract, *, session: Any, run_id: str | None):
    if snowflake_source_type(semantic) == "rest_api":
        return materialize_rest_api_source(contract=semantic, session=session, run_id=run_id)
    return render_snowflake_source(semantic)


def _apply_post_write_effects(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str | None,
) -> SnowflakePostWriteEffects:
    annotation_commands: tuple[str, ...] = ()
    if contract.governance and contract.governance.annotations:
        if not run_id:
            raise ValueError("Snowflake annotation execution requires run_id")
        annotations = apply_snowflake_annotations(session=session, environment=environment, contract=contract, run_id=run_id)
        annotation_commands = annotations.commands

    access_commands: tuple[str, ...] = ()
    if contract.governance and contract.governance.access:
        if not run_id:
            raise ValueError("Snowflake access execution requires run_id")
        access = apply_snowflake_access(session=session, environment=environment, contract=contract, run_id=run_id)
        access_commands = access.commands

    operations_commands: tuple[str, ...] = ()
    if contract.operations and contract.operations.metadata:
        if not run_id:
            raise ValueError("Snowflake operations evidence requires run_id")
        operations = record_snowflake_operations(session=session, environment=environment, contract=contract, run_id=run_id)
        operations_commands = operations.commands

    return SnowflakePostWriteEffects(
        annotation_commands=annotation_commands,
        access_commands=access_commands,
        operations_commands=operations_commands,
    )


def _record_runtime_evidence(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str | None,
    rows_read: int,
    rows_to_write: int,
    write_result: SnowflakeStatementResult,
    statement_results: tuple[SnowflakeStatementResult, ...],
    snowflake_context: dict[str, Any],
    write_started_at: str,
    write_finished_at: str,
    source_metadata: dict[str, Any],
    schema_changes: dict[str, Any],
    quality_status: str,
    quality_results: tuple[dict[str, Any], ...],
    explain_metrics: dict[str, Any],
    extra_metrics: dict[str, Any] | None = None,
    source_sql: str,
) -> SnowflakeRuntimeEvidenceResult:
    if not run_id:
        return SnowflakeRuntimeEvidenceResult()

    metrics = _runtime_metrics(
        contract=contract,
        rows_read=rows_read,
        rows_to_write=rows_to_write,
        write_result=write_result,
        statement_results=statement_results,
        snowflake_context=snowflake_context,
        command_count=0,
        write_started_at=write_started_at,
        write_finished_at=write_finished_at,
        source_metadata=source_metadata,
        schema_changes=schema_changes,
        quality_status=quality_status,
        quality_results=quality_results,
        extra_metrics={**explain_metrics, **(extra_metrics or {})},
    )
    lineage = record_lineage_evidence(
        session,
        environment=environment,
        contract=contract,
        run_id=run_id,
        source_metadata=source_metadata,
        metrics=metrics,
    )
    state = record_snowflake_state(
        session=session,
        environment=environment,
        contract=contract,
        run_id=run_id,
        status="SUCCESS",
        source_sql=source_sql,
    )
    return SnowflakeRuntimeEvidenceResult(
        lineage_commands=lineage.commands,
        state_commands=state.commands,
        metrics=metrics,
    )


def _count_sql(source_sql: str) -> str:
    return f"SELECT COUNT(*) FROM (\n{source_sql}\n) AS _CF_SOURCE"


def _capture_explain(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    statement: str,
) -> SnowflakeRuntimeEvidenceCapture:
    explain_format = _explain_format(contract)
    explain_sql = f"EXPLAIN USING {explain_format} {statement}"
    try:
        rows = session.sql(explain_sql).collect()
        plan_text = _explain_plan_text(rows)
        evidence = record_explain_evidence(
            session,
            environment=environment,
            contract=contract,
            run_id=run_id,
            plan_text=plan_text,
            explain_format=explain_format,
        )
    except Exception as exc:
        return SnowflakeRuntimeEvidenceCapture(
            commands=(explain_sql,),
            metrics={"explain_status": "FAILED", "explain_error": redact_text(str(exc))},
        )
    return SnowflakeRuntimeEvidenceCapture(
        commands=(explain_sql, *evidence.commands),
        metrics={"explain_status": "RECORDED", "explain_format": explain_format},
    )


def _explain_enabled(contract: SemanticContract) -> bool:
    snowflake = _snowflake_extensions(contract)
    return bool(snowflake.get("explain_enabled", True))


def _explain_format(contract: SemanticContract) -> str:
    value = str(_snowflake_extensions(contract).get("explain_format") or "TEXT").upper()
    if value not in {"TEXT", "JSON", "TABULAR"}:
        raise ValueError(f"Unsupported Snowflake explain format: {value}")
    return value


def _snowflake_extensions(contract: SemanticContract) -> dict[str, Any]:
    return snowflake_extensions(contract)


def _explain_plan_text(rows: Any) -> str:
    parts: list[str] = []
    for row in rows or ():
        values = _row_values(row)
        if values:
            parts.append(str(values[-1]))
    return "\n".join(parts)


def _scalar_int(session: Any, sql: str) -> int:
    return int(scalar_value(session, sql, key="COUNT") or 0)


def _query_tag_sql(contract: SemanticContract, *, run_id: str | None, target: str) -> str:
    payload = {
        "product": "contractforge",
        "adapter": "snowflake",
        "run_id": run_id,
        "target": _query_tag_target(target),
        "write_mode": contract.write.mode,
    }
    return "ALTER SESSION SET QUERY_TAG = " + sql_string(json.dumps(payload, sort_keys=True))


def _query_tag_target(target: str) -> str:
    return target.replace('"', "")


def _execute(session: Any, command: str) -> SnowflakeStatementResult:
    result = session.sql(command)
    if hasattr(result, "collect"):
        result.collect()
    query_id = _result_query_id(result) or _last_query_id(session)
    return SnowflakeStatementResult(
        command=command,
        query_id=query_id,
        rowcount=_result_rowcount(result),
    )


def _snowflake_context_sql() -> str:
    return "SELECT CURRENT_WAREHOUSE(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_VERSION()"


def _snowflake_context(session: Any, command: str) -> dict[str, str | None]:
    rows = session.sql(command).collect()
    values = _row_values(rows[0]) if rows else ()
    keys = ("warehouse", "role", "database", "schema", "version")
    return {key: _string_or_none(values[index] if index < len(values) else None) for index, key in enumerate(keys)}


def _runtime_metrics(
    *,
    contract: SemanticContract,
    rows_read: int,
    rows_to_write: int,
    write_result: SnowflakeStatementResult,
    statement_results: tuple[SnowflakeStatementResult, ...],
    snowflake_context: dict[str, str | None],
    command_count: int,
    write_started_at: str,
    write_finished_at: str,
    source_metadata: dict[str, Any],
    schema_changes: dict[str, Any],
    quality_status: str,
    quality_results: tuple[dict[str, Any], ...],
    extra_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows_written = _rows_written(contract, rows_to_write=rows_to_write, write_rowcount=write_result.rowcount)
    row_metrics = _row_metrics(contract, rows_written=rows_written, write_rowcount=write_result.rowcount)
    query_ids = [result.query_id for result in statement_results if result.query_id]
    return {
        **row_metrics,
        "rows_read": rows_read,
        "rows_written": rows_written,
        "rows_quarantined": max(rows_read - rows_to_write, 0),
        "write_started_at_utc": write_started_at,
        "write_finished_at_utc": write_finished_at,
        "write_query_id": write_result.query_id,
        "write_rowcount": write_result.rowcount,
        "query_ids": query_ids,
        "query_count": len(query_ids),
        "command_count": command_count,
        "quality_status": quality_status,
        "quality_results": list(quality_results),
        "schema_changes": schema_changes,
        "source": source_metadata,
        "snowflake": snowflake_context,
        "metrics_source": "snowflake_connector" if write_result.rowcount is not None else "snowflake_logical_count",
        **_idempotency_metrics(contract),
        **(extra_metrics or {}),
    }


def _rows_written(contract: SemanticContract, *, rows_to_write: int, write_rowcount: int | None) -> int:
    if contract.write.mode in {"append", "scd0_append", "overwrite", "scd0_overwrite"}:
        return rows_to_write
    if write_rowcount is not None:
        return write_rowcount
    if contract.write.mode in {"scd1_upsert", "scd1_hash_diff"}:
        return rows_to_write
    return 0


def _row_metrics(contract: SemanticContract, *, rows_written: int, write_rowcount: int | None) -> dict[str, int | None]:
    if contract.write.mode in {"append", "scd0_append", "overwrite", "scd0_overwrite"}:
        return {"rows_inserted": rows_written, "rows_updated": 0, "rows_deleted": 0}
    return {
        "rows_inserted": None,
        "rows_updated": None,
        "rows_deleted": 0,
        "rows_affected": write_rowcount,
    }


def _idempotency_metrics(contract: SemanticContract) -> dict[str, str]:
    metadata = contract.operations.metadata or {}
    payload: dict[str, str] = {}
    key = metadata.get("idempotency_key")
    policy = metadata.get("idempotency_policy")
    if key not in (None, ""):
        payload["idempotency_key"] = str(key)
    if policy not in (None, ""):
        payload["idempotency_policy"] = str(policy)
    return payload


def _result_query_id(result: Any) -> str | None:
    value = getattr(result, "query_id", None) or getattr(result, "sfqid", None)
    return str(value) if value else None


def _last_query_id(session: Any) -> str | None:
    try:
        rows = session.sql("SELECT LAST_QUERY_ID()").collect()
    except Exception:
        return None
    if not rows:
        return None
    values = _row_values(rows[0])
    return str(values[0]) if values and values[0] else None


def _result_rowcount(result: Any) -> int | None:
    value = getattr(result, "rowcount", None)
    if value is None:
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count >= 0 else None


def _row_values(row: Any) -> tuple[Any, ...]:
    if isinstance(row, dict):
        return tuple(row.values())
    try:
        return tuple(row)
    except TypeError:
        return (row,)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


__all__ = ["SnowflakeExecutionResult", "SnowflakeStatementResult", "execute_snowflake_contract"]
