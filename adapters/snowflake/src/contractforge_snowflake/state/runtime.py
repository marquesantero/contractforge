"""Snowflake state and watermark handling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from contractforge_core.evidence.control_tables import STATE_TABLES
from contractforge_core.security.redaction import redact_text
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.naming import quote_identifier, snowflake_target_name
from contractforge_snowflake.session_ops import execute
from contractforge_snowflake.sql import sql_string
from contractforge_snowflake.values import dict_mapping as _mapping
from contractforge_snowflake.values import string_or_none as _string_or_none


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class SnowflakeStateResult:
    source_sql: str
    commands: tuple[str, ...]


@dataclass(frozen=True)
class SnowflakeIdempotencyResult:
    command: str | None
    run_id: str | None
    status: str | None


@dataclass(frozen=True)
class SnowflakeLockResult:
    commands: tuple[str, ...]
    status: str = "SUCCESS"
    warning: str | None = None


def find_idempotent_run(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    status: str = "SUCCESS",
) -> SnowflakeIdempotencyResult:
    key, policy = _idempotency(contract)
    if not key or policy not in {"skip_if_success", "rerun_if_failed", "fail_if_success"}:
        return SnowflakeIdempotencyResult(command=None, run_id=None, status=None)
    command = _find_idempotent_run_sql(environment=environment, contract=contract, idempotency_key=key, status=status)
    rows = session.sql(command).collect()
    if not rows:
        return SnowflakeIdempotencyResult(command=command, run_id=None, status=None)
    row = _row_mapping(rows[0])
    return SnowflakeIdempotencyResult(
        command=command,
        run_id=_string_or_none(row.get("RUN_ID") or row.get("run_id")),
        status=_string_or_none(row.get("STATUS") or row.get("status")),
    )


def acquire_snowflake_lock(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    target_table: str,
    run_id: str,
    owner: str | None = None,
    ttl_minutes: int = 60,
) -> SnowflakeLockResult:
    acquire = _acquire_lock_sql(
        environment=environment,
        target_table=target_table,
        run_id=run_id,
        owner=owner,
        ttl_minutes=ttl_minutes,
    )
    execute(session, acquire)
    status_sql = _lock_status_sql(environment=environment, target_table=target_table)
    rows = session.sql(status_sql).collect()
    row = _row_mapping(rows[0]) if rows else {}
    active_run = _string_or_none(row.get("RUN_ID") or row.get("run_id"))
    active_status = _string_or_none(row.get("STATUS") or row.get("status"))
    if active_run not in (None, run_id) or active_status not in (None, "ACTIVE"):
        raise RuntimeError(f"Snowflake lock is busy for {target_table}. This run_id={run_id} did not acquire the lock.")
    return SnowflakeLockResult(commands=(acquire, status_sql), status="ACQUIRED")


def release_snowflake_lock(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    target_table: str,
    run_id: str,
) -> SnowflakeLockResult:
    command = _release_lock_sql(environment=environment, target_table=target_table, run_id=run_id)
    try:
        execute(session, command)
    except Exception as exc:
        warning = f"lock_release_failed: {type(exc).__name__}: {redact_text(str(exc))}"
        return SnowflakeLockResult(commands=(command,), status="FAILED", warning=warning)
    return SnowflakeLockResult(commands=(command,), status="RELEASED")


def apply_snowflake_state_filter(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    source_sql: str,
) -> SnowflakeStateResult:
    """Apply the previous successful watermark to source SQL when declared."""

    column = _watermark_column(contract)
    if not column:
        return SnowflakeStateResult(source_sql=source_sql, commands=())
    previous_sql = _previous_watermark_sql(environment=environment, contract=contract, column=column)
    previous = _scalar_string(session, previous_sql)
    if previous in (None, ""):
        return SnowflakeStateResult(source_sql=source_sql, commands=(previous_sql,))
    filtered = (
        "SELECT * FROM (\n"
        f"{source_sql}\n"
        ") AS _CF_SOURCE\n"
        f"WHERE {quote_identifier(column)} > {sql_string(previous)}"
    )
    return SnowflakeStateResult(source_sql=filtered, commands=(previous_sql,))


def record_snowflake_state(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    status: str,
    source_sql: str | None,
    error_message: str | None = None,
) -> SnowflakeStateResult:
    """Append a canonical state row for the target table."""

    column = _watermark_column(contract)
    candidate_sql = _candidate_watermark_sql(source_sql=source_sql, column=column) if column and source_sql else None
    candidate = _scalar_string(session, candidate_sql) if candidate_sql else None
    command = _insert_state_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        status=status,
        watermark_column=column,
        watermark_candidate=candidate,
        error_message=error_message,
    )
    execute(session, command)
    return SnowflakeStateResult(source_sql=source_sql or "", commands=tuple(item for item in (candidate_sql, command) if item))


def _watermark_column(contract: SemanticContract) -> str | None:
    source = contract.source.raw or {}
    incremental = _mapping(source.get("incremental"))
    watermark = _mapping(source.get("watermark"))
    column = incremental.get("watermark_column") or watermark.get("column") or watermark.get("watermark_column")
    if column is None:
        return None
    text = str(column).strip()
    if not _IDENTIFIER_RE.match(text):
        raise ValueError("Snowflake source.incremental.watermark_column must be a simple identifier")
    return text


def _previous_watermark_sql(*, environment: SnowflakeEnvironment, contract: SemanticContract, column: str) -> str:
    return (
        f"SELECT {quote_identifier('watermark_value')} FROM {_state_table(environment)}\n"
        f"WHERE {quote_identifier('target_table')} = {sql_string(snowflake_target_name(contract))}\n"
        f"  AND {quote_identifier('watermark_column')} = {sql_string(column)}\n"
        f"  AND {quote_identifier('last_status')} = 'SUCCESS'\n"
        f"ORDER BY {quote_identifier('last_updated_at_utc')} DESC\n"
        "LIMIT 1"
    )


def _candidate_watermark_sql(*, source_sql: str, column: str) -> str:
    return f"SELECT MAX({quote_identifier(column)}) FROM (\n{source_sql}\n) AS _CF_SOURCE"


def _insert_state_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    status: str,
    watermark_column: str | None,
    watermark_candidate: str | None,
    error_message: str | None,
) -> str:
    columns = (
        "target_table",
        "watermark_column",
        "watermark_value",
        "last_success_at_utc",
        "last_run_id",
        "last_status",
        "last_rows_written",
        "last_error_message",
        "last_table_version",
        "last_write_completed_at_utc",
        "last_watermark_candidate",
        "last_updated_at_utc",
    )
    values = (
        sql_string(snowflake_target_name(contract)),
        sql_string(watermark_column),
        sql_string(watermark_candidate),
        "CURRENT_TIMESTAMP()" if status == "SUCCESS" else "NULL",
        sql_string(run_id),
        sql_string(status),
        "NULL",
        sql_string(redact_text(error_message) if error_message else None),
        "NULL",
        "CURRENT_TIMESTAMP()" if status == "SUCCESS" else "NULL",
        sql_string(watermark_candidate),
        "CURRENT_TIMESTAMP()",
    )
    return (
        f"INSERT INTO {_state_table(environment)} ({', '.join(quote_identifier(column) for column in columns)})\n"
        f"SELECT {', '.join(values)}"
    )


def _state_table(environment: SnowflakeEnvironment) -> str:
    return _table(environment, STATE_TABLES["state"])


def _runs_table(environment: SnowflakeEnvironment) -> str:
    return _table(environment, "ctrl_ingestion_runs")


def _locks_table(environment: SnowflakeEnvironment) -> str:
    return _table(environment, STATE_TABLES["locks"])


def _table(environment: SnowflakeEnvironment, table_name: str) -> str:
    return ".".join(
        quote_identifier(part)
        for part in (
            environment.evidence_database or "CONTRACTFORGE",
            environment.evidence_schema or "CF_EVIDENCE",
            table_name,
        )
    )


def _find_idempotent_run_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    idempotency_key: str,
    status: str,
) -> str:
    return (
        f"SELECT {quote_identifier('run_id')}, {quote_identifier('status')}\n"
        f"FROM {_runs_table(environment)}\n"
        f"WHERE {quote_identifier('target_table')} = {sql_string(snowflake_target_name(contract))}\n"
        f"  AND {quote_identifier('idempotency_key')} = {sql_string(idempotency_key)}\n"
        f"  AND {quote_identifier('status')} = {sql_string(status)}\n"
        f"ORDER BY {quote_identifier('run_ts_utc')} DESC NULLS LAST\n"
        "LIMIT 1"
    )


def _acquire_lock_sql(
    *,
    environment: SnowflakeEnvironment,
    target_table: str,
    run_id: str,
    owner: str | None,
    ttl_minutes: int,
) -> str:
    return f"""
MERGE INTO {_locks_table(environment)} AS target
USING (
  SELECT
    {sql_string(target_table)} AS {quote_identifier('target_table')},
    {sql_string(run_id)} AS {quote_identifier('run_id')},
    {sql_string(owner)} AS {quote_identifier('owner')},
    CURRENT_TIMESTAMP() AS {quote_identifier('acquired_at_utc')},
    DATEADD(minute, {int(ttl_minutes)}, CURRENT_TIMESTAMP()) AS {quote_identifier('expires_at_utc')},
    {int(ttl_minutes)} AS {quote_identifier('ttl_minutes')},
    NULL AS {quote_identifier('released_at_utc')},
    'ACTIVE' AS {quote_identifier('status')}
) AS source
ON target.{quote_identifier('target_table')} = source.{quote_identifier('target_table')}
WHEN MATCHED AND (target.{quote_identifier('status')} <> 'ACTIVE' OR target.{quote_identifier('expires_at_utc')} < CURRENT_TIMESTAMP()) THEN UPDATE SET
  {quote_identifier('run_id')} = source.{quote_identifier('run_id')},
  {quote_identifier('owner')} = source.{quote_identifier('owner')},
  {quote_identifier('acquired_at_utc')} = source.{quote_identifier('acquired_at_utc')},
  {quote_identifier('expires_at_utc')} = source.{quote_identifier('expires_at_utc')},
  {quote_identifier('ttl_minutes')} = source.{quote_identifier('ttl_minutes')},
  {quote_identifier('released_at_utc')} = source.{quote_identifier('released_at_utc')},
  {quote_identifier('status')} = source.{quote_identifier('status')}
WHEN NOT MATCHED THEN INSERT ({quote_identifier('target_table')}, {quote_identifier('run_id')}, {quote_identifier('owner')}, {quote_identifier('acquired_at_utc')}, {quote_identifier('expires_at_utc')}, {quote_identifier('ttl_minutes')}, {quote_identifier('released_at_utc')}, {quote_identifier('status')})
VALUES (source.{quote_identifier('target_table')}, source.{quote_identifier('run_id')}, source.{quote_identifier('owner')}, source.{quote_identifier('acquired_at_utc')}, source.{quote_identifier('expires_at_utc')}, source.{quote_identifier('ttl_minutes')}, source.{quote_identifier('released_at_utc')}, source.{quote_identifier('status')})
""".strip()


def _release_lock_sql(*, environment: SnowflakeEnvironment, target_table: str, run_id: str) -> str:
    return (
        f"UPDATE {_locks_table(environment)}\n"
        f"SET {quote_identifier('status')} = 'RELEASED', {quote_identifier('released_at_utc')} = CURRENT_TIMESTAMP()\n"
        f"WHERE {quote_identifier('target_table')} = {sql_string(target_table)} AND {quote_identifier('run_id')} = {sql_string(run_id)}"
    )


def _lock_status_sql(*, environment: SnowflakeEnvironment, target_table: str) -> str:
    return (
        f"SELECT {quote_identifier('run_id')}, {quote_identifier('owner')}, {quote_identifier('status')}, {quote_identifier('acquired_at_utc')}, {quote_identifier('expires_at_utc')}, {quote_identifier('ttl_minutes')}\n"
        f"FROM {_locks_table(environment)}\n"
        f"WHERE {quote_identifier('target_table')} = {sql_string(target_table)}\n"
        "LIMIT 1"
    )


def _scalar_string(session: Any, sql: str) -> str | None:
    rows = session.sql(sql).collect()
    if not rows:
        return None
    row = rows[0]
    if isinstance(row, dict):
        value = next(iter(row.values()), None)
    else:
        try:
            value = row[0]
        except (TypeError, KeyError, IndexError):
            value = getattr(row, "WATERMARK_VALUE", None)
    return None if value is None else str(value)


def _row_mapping(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return {str(key): value for key, value in row.items()}
    try:
        values = tuple(row)
    except TypeError:
        return {}
    keys = ("RUN_ID", "STATUS", "OWNER", "ACQUIRED_AT_UTC", "EXPIRES_AT_UTC", "TTL_MINUTES")
    return {key: values[index] for index, key in enumerate(keys) if index < len(values)}


def _idempotency(contract: SemanticContract) -> tuple[str | None, str]:
    metadata = contract.operations.metadata or {}
    key = metadata.get("idempotency_key")
    policy = metadata.get("idempotency_policy") or "always_run"
    return (str(key) if key not in (None, "") else None, str(policy))


__all__ = [
    "SnowflakeStateResult",
    "SnowflakeIdempotencyResult",
    "SnowflakeLockResult",
    "acquire_snowflake_lock",
    "apply_snowflake_state_filter",
    "find_idempotent_run",
    "record_snowflake_state",
    "release_snowflake_lock",
]
