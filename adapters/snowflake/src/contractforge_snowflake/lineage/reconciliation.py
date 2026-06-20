"""Reconcile delayed Snowflake Access History lineage into evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.security.redaction import redact_text
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.session_ops import execute, scalar_int
from contractforge_snowflake.sql import sql_string


@dataclass(frozen=True)
class SnowflakeAccessHistoryLineageResult:
    status: str
    commands: tuple[str, ...]
    row_count: int = 0
    warnings: tuple[str, ...] = ()


def reconcile_snowflake_access_history_lineage(
    *,
    session: Any,
    environment: SnowflakeEnvironment | dict[str, Any] | None,
    run_id: str,
) -> SnowflakeAccessHistoryLineageResult:
    env = environment if isinstance(environment, SnowflakeEnvironment) else SnowflakeEnvironment.from_contract(environment)
    probe = _probe_sql(run_id=run_id)
    try:
        row_count = scalar_int(session, probe, key="ACCESS_HISTORY_ROWS")
    except Exception as exc:
        warning = _warning("access_history_unavailable", exc)
        return SnowflakeAccessHistoryLineageResult(status="PENDING", commands=(probe,), warnings=(warning,))
    if row_count < 1:
        return SnowflakeAccessHistoryLineageResult(status="PENDING", commands=(probe,), row_count=0)
    insert = _insert_sql(environment=env, run_id=run_id)
    execute(session, insert)
    return SnowflakeAccessHistoryLineageResult(status="RECORDED", commands=(probe, insert), row_count=row_count)


def _probe_sql(*, run_id: str) -> str:
    return "\n".join(
        (
            "SELECT COUNT(*) AS ACCESS_HISTORY_ROWS",
            "FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah",
            "JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh ON qh.query_id = ah.query_id",
            f"WHERE TRY_PARSE_JSON(qh.query_tag):run_id::STRING = {sql_string(run_id)}",
        )
    )


def _insert_sql(*, environment: SnowflakeEnvironment, run_id: str) -> str:
    query_filter = f"TRY_PARSE_JSON(qh.query_tag):run_id::STRING = {sql_string(run_id)}"
    return "\n".join(
        (
            f"INSERT INTO {_table(environment)} (",
            '  "run_id", "event_time_utc", "event_type", "target_table", "source_table", "source_name", "namespace", "producer", "event_json"',
            ")",
            "SELECT",
            f"  {sql_string(run_id)},",
            "  CURRENT_TIMESTAMP(),",
            "  'NATIVE_ACCESS_HISTORY',",
            "  MAX(TRY_PARSE_JSON(qh.query_tag):target::STRING),",
            "  NULL,",
            "  'SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY',",
            "  'snowflake_access_history',",
            "  'contractforge-snowflake',",
            "  TO_JSON(OBJECT_CONSTRUCT_KEEP_NULL(",
            "    'source', 'SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY',",
            "    'query_count', COUNT(DISTINCT ah.query_id),",
            "    'access_history_rows', COUNT(*),",
            "    'base_objects_accessed', ARRAY_AGG(ah.base_objects_accessed),",
            "    'objects_modified', ARRAY_AGG(ah.objects_modified)",
            "  ))",
            "FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah",
            "JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh ON qh.query_id = ah.query_id",
            f"WHERE {query_filter}",
        )
    )


def _table(environment: SnowflakeEnvironment) -> str:
    return ".".join(
        quote_identifier(part)
        for part in (
            environment.evidence_database or "CONTRACTFORGE",
            environment.evidence_schema or "CF_EVIDENCE",
            "ctrl_ingestion_lineage",
        )
    )


def _warning(prefix: str, exc: Exception) -> str:
    return f"{prefix}: {type(exc).__name__}: {redact_text(str(exc))}"
