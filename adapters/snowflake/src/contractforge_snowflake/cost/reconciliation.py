"""Reconcile Snowflake query-history cost signals into ContractForge evidence."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from contractforge_core.evidence.control_tables import EVIDENCE_TABLES
from contractforge_core.security.redaction import redact_text
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.polling import clamped_poll_interval
from contractforge_snowflake.session_ops import execute, scalar_int
from contractforge_snowflake.sql import sql_string


@dataclass(frozen=True)
class SnowflakeCostReconciliationResult:
    status: str
    commands: tuple[str, ...]
    query_count: int = 0
    warnings: tuple[str, ...] = ()


def reconcile_snowflake_cost_evidence(
    *,
    session: Any,
    environment: SnowflakeEnvironment | dict[str, Any] | None,
    run_id: str,
    target_table: str,
    wait: bool = False,
    poll_interval_seconds: float = 30.0,
    max_wait_seconds: float = 0.0,
) -> SnowflakeCostReconciliationResult:
    """Record delayed Snowflake query-history cost signals for a run.

    Snowflake Account Usage is eventually available, so this helper is intended
    for post-run reconciliation rather than inline ingestion finalization.
    """

    env = environment if isinstance(environment, SnowflakeEnvironment) else SnowflakeEnvironment.from_contract(environment)
    tag_filter = _query_tag_filter(run_id=run_id)
    query_filter = tag_filter
    probe = _cost_probe_sql(query_filter=tag_filter)
    probe_commands = [probe]
    try:
        query_count = _wait_for_query_history(
            session,
            probe,
            wait=wait,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
        )
    except Exception as exc:
        warning = _warning("query_history_unavailable", exc)
        return SnowflakeCostReconciliationResult(status="PENDING", commands=(probe,), query_count=0, warnings=(warning,))
    if query_count < 1:
        query_id_filter = _query_id_filter(environment=env, run_id=run_id)
        query_id_probe = _cost_probe_sql(query_filter=query_id_filter)
        probe_commands.append(query_id_probe)
        try:
            query_count = _wait_for_query_history(
                session,
                query_id_probe,
                wait=wait,
                poll_interval_seconds=poll_interval_seconds,
                max_wait_seconds=max_wait_seconds,
            )
        except Exception as exc:
            warning = _warning("query_id_history_unavailable", exc)
            return SnowflakeCostReconciliationResult(status="PENDING", commands=tuple(probe_commands), query_count=0, warnings=(warning,))
        if query_count < 1:
            return SnowflakeCostReconciliationResult(status="PENDING", commands=tuple(probe_commands), query_count=0)
        query_filter = query_id_filter
    delete = _cost_delete_sql(environment=env, run_id=run_id, target_table=target_table)
    history = _cost_history_sql(environment=env, run_id=run_id, target_table=target_table, query_filter=query_filter)
    commands = [*probe_commands, delete, history]
    execute(session, delete)
    execute(session, history)
    warnings: list[str] = []
    attribution = _cost_attribution_sql(environment=env, run_id=run_id, target_table=target_table, query_filter=query_filter)
    try:
        execute(session, attribution)
    except Exception as exc:
        warnings.append(_warning("query_attribution_history_unavailable", exc))
    else:
        commands.append(attribution)
    return SnowflakeCostReconciliationResult(
        status="RECORDED_WITH_WARNINGS" if warnings else "RECORDED",
        commands=tuple(commands),
        query_count=query_count,
        warnings=tuple(warnings),
    )


def _cost_probe_sql(*, query_filter: str) -> str:
    return "\n".join(
        (
            "SELECT COUNT(*) AS QUERY_COUNT",
            "FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY",
            f"WHERE {query_filter}",
        )
    )


def _cost_delete_sql(*, environment: SnowflakeEnvironment, run_id: str, target_table: str) -> str:
    signal_names = (
        "query_count",
        "bytes_scanned",
        "execution_time_ms",
        "cloud_services_credits",
        "rows_produced",
        "warehouse_count",
        "attributed_compute_credits",
        "query_acceleration_credits",
    )
    signals = ", ".join(sql_string(signal) for signal in signal_names)
    return (
        f"DELETE FROM {_table(environment)}\n"
        f"WHERE \"run_id\" = {sql_string(run_id)}\n"
        f"  AND \"target_table\" = {sql_string(target_table)}\n"
        f"  AND \"signal_name\" IN ({signals})"
    )


def _cost_history_sql(
    *,
    environment: SnowflakeEnvironment,
    run_id: str,
    target_table: str,
    query_filter: str,
) -> str:
    table = _table(environment)
    run_literal = sql_string(run_id)
    target_literal = sql_string(target_table)
    payload = (
        "TO_JSON(OBJECT_CONSTRUCT_KEEP_NULL('source', 'SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY', "
        "'match', 'query_tag.run_id_or_ctrl_ingestion_runs.metrics_json.query_ids'))"
    )
    return "\n".join(
        (
            f"INSERT INTO {table} (",
            '  "run_id", "target_table", "signal_name", "signal_value", "payload_json", "captured_at_utc"',
            ")",
            f"SELECT {run_literal}, {target_literal}, signal_name, signal_value, {payload}, CURRENT_TIMESTAMP()",
            "FROM (",
            "  SELECT 'query_count' AS signal_name, COUNT(*)::DOUBLE AS signal_value",
            "  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY",
            f"  WHERE {query_filter}",
            "  UNION ALL",
            "  SELECT 'bytes_scanned' AS signal_name, COALESCE(SUM(bytes_scanned), 0)::DOUBLE AS signal_value",
            "  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY",
            f"  WHERE {query_filter}",
            "  UNION ALL",
            "  SELECT 'execution_time_ms' AS signal_name, COALESCE(SUM(execution_time), 0)::DOUBLE AS signal_value",
            "  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY",
            f"  WHERE {query_filter}",
            "  UNION ALL",
            "  SELECT 'cloud_services_credits' AS signal_name, COALESCE(SUM(credits_used_cloud_services), 0)::DOUBLE AS signal_value",
            "  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY",
            f"  WHERE {query_filter}",
            "  UNION ALL",
            "  SELECT 'rows_produced' AS signal_name, COALESCE(SUM(rows_produced), 0)::DOUBLE AS signal_value",
            "  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY",
            f"  WHERE {query_filter}",
            "  UNION ALL",
            "  SELECT 'warehouse_count' AS signal_name, COUNT(DISTINCT warehouse_name)::DOUBLE AS signal_value",
            "  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY",
            f"  WHERE {query_filter}",
            ") AS signals",
        )
    )


def _cost_attribution_sql(
    *,
    environment: SnowflakeEnvironment,
    run_id: str,
    target_table: str,
    query_filter: str,
) -> str:
    table = _table(environment)
    run_literal = sql_string(run_id)
    target_literal = sql_string(target_table)
    payload = (
        "TO_JSON(OBJECT_CONSTRUCT_KEEP_NULL('source', 'SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY', "
        "'match', 'query_tag.run_id_or_ctrl_ingestion_runs.metrics_json.query_ids'))"
    )
    return "\n".join(
        (
            f"INSERT INTO {table} (",
            '  "run_id", "target_table", "signal_name", "signal_value", "payload_json", "captured_at_utc"',
            ")",
            f"SELECT {run_literal}, {target_literal}, signal_name, signal_value, {payload}, CURRENT_TIMESTAMP()",
            "FROM (",
            "  SELECT 'attributed_compute_credits' AS signal_name, COALESCE(SUM(credits_attributed_compute), 0)::DOUBLE AS signal_value",
            "  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY",
            f"  WHERE {query_filter}",
            "  UNION ALL",
            "  SELECT 'query_acceleration_credits' AS signal_name, COALESCE(SUM(credits_used_query_acceleration), 0)::DOUBLE AS signal_value",
            "  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY",
            f"  WHERE {query_filter}",
            ") AS signals",
        )
    )


def _query_tag_filter(*, run_id: str) -> str:
    return f"TRY_PARSE_JSON(query_tag):run_id::STRING = {sql_string(run_id)}"


def _query_id_filter(*, environment: SnowflakeEnvironment, run_id: str) -> str:
    return f"query_id IN ({_run_query_ids_sql(environment=environment, run_id=run_id)})"


def _run_query_ids_sql(*, environment: SnowflakeEnvironment, run_id: str) -> str:
    return "\n".join(
        (
            "SELECT value::STRING",
            f"FROM {_runs_table(environment)},",
            "     LATERAL FLATTEN(input => TRY_PARSE_JSON(\"metrics_json\"):query_ids)",
            f"WHERE \"run_id\" = {sql_string(run_id)}",
        )
    )


def _table(environment: SnowflakeEnvironment) -> str:
    return ".".join(
        quote_identifier(part)
        for part in (
            environment.evidence_database or "CONTRACTFORGE",
            environment.evidence_schema or "CF_EVIDENCE",
            EVIDENCE_TABLES["cost"],
        )
    )


def _runs_table(environment: SnowflakeEnvironment) -> str:
    return ".".join(
        quote_identifier(part)
        for part in (
            environment.evidence_database or "CONTRACTFORGE",
            environment.evidence_schema or "CF_EVIDENCE",
            EVIDENCE_TABLES["runs"],
        )
    )


def _warning(prefix: str, exc: Exception) -> str:
    return f"{prefix}: {type(exc).__name__}: {redact_text(str(exc))}"


def _wait_for_query_history(
    session: Any,
    command: str,
    *,
    wait: bool,
    poll_interval_seconds: float,
    max_wait_seconds: float,
) -> int:
    deadline = time.monotonic() + max_wait_seconds
    poll_interval = clamped_poll_interval(poll_interval_seconds)
    while True:
        count = scalar_int(session, command, key="QUERY_COUNT")
        if count > 0 or not wait or time.monotonic() >= deadline:
            return count
        time.sleep(poll_interval)


__all__ = ["SnowflakeCostReconciliationResult", "reconcile_snowflake_cost_evidence"]
