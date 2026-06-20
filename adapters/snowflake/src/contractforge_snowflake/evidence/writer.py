"""Snowflake evidence writers for core control-table schemas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from contractforge_core.evidence.control_tables import EVIDENCE_TABLES
from contractforge_core.security.redaction import redact_text
from contractforge_core.semantic import QualityIntent, SemanticContract
from contractforge_snowflake.contract_extensions import snowflake_extensions
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence.ddl import render_create_evidence_tables_sql, render_create_state_tables_sql
from contractforge_snowflake.naming import quote_identifier, snowflake_target_name
from contractforge_snowflake.session_ops import execute
from contractforge_snowflake.sql import sql_string


@dataclass(frozen=True)
class SnowflakeEvidenceResult:
    commands: tuple[str, ...]
    skipped_commands: tuple[str, ...] = ()


def bootstrap_evidence_tables(session: Any, environment: SnowflakeEnvironment) -> SnowflakeEvidenceResult:
    database = _database(environment)
    schema = _schema(environment)
    commands = tuple(
        _split_statements(
            render_create_evidence_tables_sql(
                database=database,
                schema=schema,
                create_database=environment.evidence_create_database,
                create_schema=environment.evidence_create_schema,
            )
            + "\n"
            + render_create_state_tables_sql(
                database=database,
                schema=schema,
                create_database=environment.evidence_create_database,
                create_schema=environment.evidence_create_schema,
            )
        )
    )
    skipped_commands = _skipped_bootstrap_commands(environment, database=database, schema=schema)
    if environment.evidence_validate_only_ddl:
        return SnowflakeEvidenceResult(commands=commands, skipped_commands=skipped_commands)
    for command in commands:
        _execute(session, command)
    return SnowflakeEvidenceResult(commands=commands, skipped_commands=skipped_commands)


def _skipped_bootstrap_commands(
    environment: SnowflakeEnvironment,
    *,
    database: str,
    schema: str,
) -> tuple[str, ...]:
    skipped: list[str] = []
    if not environment.evidence_create_database:
        skipped.append(f"CREATE DATABASE IF NOT EXISTS {quote_identifier(database)}")
    if not environment.evidence_create_schema:
        skipped.append(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(database)}.{quote_identifier(schema)}")
    return tuple(skipped)


def record_run_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    status: str,
    error_message: str | None = None,
    command_count: int = 0,
    metrics: dict[str, Any] | None = None,
) -> SnowflakeEvidenceResult:
    command = _insert_runs_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        status=status,
        error_message=error_message,
        command_count=command_count,
        metrics=metrics,
    )
    _execute(session, command)
    return SnowflakeEvidenceResult(commands=(command,))


def record_error_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    error: BaseException,
) -> SnowflakeEvidenceResult:
    command = _insert_errors_sql(environment=environment, contract=contract, run_id=run_id, error=error)
    _execute(session, command)
    return SnowflakeEvidenceResult(commands=(command,))


def record_quality_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    rule: QualityIntent,
    status: str,
    failed_count: int,
    observed_value: object | None = None,
) -> SnowflakeEvidenceResult:
    command = _insert_quality_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        rule=rule,
        status=status,
        failed_count=failed_count,
        observed_value=observed_value,
    )
    _execute(session, command)
    return SnowflakeEvidenceResult(commands=(command,))


def record_quarantine_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    rule: QualityIntent,
    source_sql: str,
    failed_condition: str,
) -> SnowflakeEvidenceResult:
    command = _insert_quarantine_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        rule=rule,
        source_sql=source_sql,
        failed_condition=failed_condition,
    )
    _execute(session, command)
    return SnowflakeEvidenceResult(commands=(command,))


def record_schema_change_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    schema_changes: dict[str, Any],
) -> SnowflakeEvidenceResult:
    commands = _insert_schema_change_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        schema_changes=schema_changes,
    )
    for command in commands:
        _execute(session, command)
    return SnowflakeEvidenceResult(commands=commands)


def record_annotation_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    step: dict[str, Any],
    status: str,
    error_message: str | None,
) -> SnowflakeEvidenceResult:
    command = _insert_annotation_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        step=step,
        status=status,
        error_message=error_message,
    )
    _execute(session, command)
    return SnowflakeEvidenceResult(commands=(command,))


def record_access_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    step: dict[str, Any],
    status: str,
    error_message: str | None,
) -> SnowflakeEvidenceResult:
    command = _insert_access_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        step=step,
        status=status,
        error_message=error_message,
    )
    _execute(session, command)
    return SnowflakeEvidenceResult(commands=(command,))


def record_operations_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    payload: dict[str, Any],
    status: str,
) -> SnowflakeEvidenceResult:
    command = _insert_operations_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        payload=payload,
        status=status,
    )
    _execute(session, command)
    return SnowflakeEvidenceResult(commands=(command,))


def record_lineage_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    source_metadata: dict[str, Any],
    metrics: dict[str, Any],
) -> SnowflakeEvidenceResult:
    command = _insert_lineage_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        source_metadata=source_metadata,
        metrics=metrics,
    )
    _execute(session, command)
    return SnowflakeEvidenceResult(commands=(command,))


def record_explain_evidence(
    session: Any,
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    plan_text: str,
    explain_format: str = "TEXT",
) -> SnowflakeEvidenceResult:
    command = _insert_explain_sql(
        environment=environment,
        contract=contract,
        run_id=run_id,
        plan_text=plan_text,
        explain_format=explain_format,
    )
    _execute(session, command)
    return SnowflakeEvidenceResult(commands=(command,))


def _insert_runs_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    status: str,
    error_message: str | None,
    command_count: int,
    metrics: dict[str, Any] | None,
) -> str:
    payload = dict(metrics or {})
    payload.setdefault("command_count", command_count)
    columns = (
        "run_id",
        "run_ts_utc",
        "run_date",
        "runtime_entrypoint",
        "layer",
        "source_table",
        "source_type",
        "target_table",
        "mode",
        "write_engine_requested",
        "write_engine_selected",
        "write_engine_status",
        "status",
        "rows_read",
        "rows_written",
        "rows_inserted",
        "rows_updated",
        "rows_deleted",
        "started_at_utc",
        "finished_at_utc",
        "write_started_at_utc",
        "write_finished_at_utc",
        "quality_status",
        "schema_policy",
        "schema_changes_json",
        "operation_metrics_json",
        "error_message",
        "idempotency_key",
        "idempotency_policy",
        "skip_reason",
        "skipped_by_run_id",
        "metrics_source",
        "runtime_type",
        "metrics_json",
    )
    values = (
        _sql_string(run_id),
        "CURRENT_TIMESTAMP()",
        "CURRENT_DATE()",
        _sql_string("contractforge_snowflake.runtime.run_snowflake_contract"),
        _sql_string(contract.target.layer),
        _sql_string(contract.source.location or contract.source.name),
        _sql_string(contract.source.kind),
        _sql_string(snowflake_target_name(contract)),
        _sql_string(contract.write.mode),
        _sql_string(contract.write.mode),
        _sql_string("snowflake_library_runner"),
        _sql_string(status),
        _sql_string(status),
        _sql_int(payload.get("rows_read")),
        _sql_int(payload.get("rows_written")),
        _sql_int(payload.get("rows_inserted")),
        _sql_int(payload.get("rows_updated")),
        _sql_int(payload.get("rows_deleted")),
        "CURRENT_TIMESTAMP()",
        "CURRENT_TIMESTAMP()",
        _sql_string(payload.get("write_started_at_utc")),
        _sql_string(payload.get("write_finished_at_utc")),
        _sql_string(payload.get("quality_status") or ("NOT_CONFIGURED" if not contract.quality else status)),
        _sql_string(contract.write.schema_policy),
        _sql_json(payload.get("schema_changes") or {}),
        _sql_json(payload),
        _sql_string(redact_text(error_message) if error_message else None),
        _sql_string(payload.get("idempotency_key")),
        _sql_string(payload.get("idempotency_policy")),
        _sql_string(payload.get("skip_reason")),
        _sql_string(payload.get("skipped_by_run_id")),
        _sql_string(payload.get("metrics_source") or "snowflake_runtime"),
        _sql_string("snowflake"),
        _sql_json(payload),
    )
    return _insert_select(_table(environment, "runs"), columns, values)


def _insert_errors_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    error: BaseException,
) -> str:
    columns = (
        "run_id",
        "error_ts_utc",
        "error_date",
        "target_table",
        "source_table",
        "mode",
        "status",
        "error_type",
        "error_class",
        "error_message",
        "occurred_at_utc",
        "runtime_type",
    )
    values = (
        _sql_string(run_id),
        "CURRENT_TIMESTAMP()",
        "CURRENT_DATE()",
        _sql_string(snowflake_target_name(contract)),
        _sql_string(contract.source.location or contract.source.name),
        _sql_string(contract.write.mode),
        _sql_string("FAILED"),
        _sql_string(type(error).__name__),
        _sql_string(type(error).__name__),
        _sql_string(redact_text(str(error))),
        "CURRENT_TIMESTAMP()",
        _sql_string("snowflake"),
    )
    return _insert_select(_table(environment, "errors"), columns, values)


def _insert_quality_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    rule: QualityIntent,
    status: str,
    failed_count: int,
    observed_value: object | None,
) -> str:
    columns = (
        "run_id",
        "target_table",
        "rule_name",
        "status",
        "severity",
        "failed_count",
        "observed_value",
        "checked_at_utc",
        "message",
        "details_json",
    )
    values = (
        _sql_string(run_id),
        _sql_string(snowflake_target_name(contract)),
        _sql_string(rule.name),
        _sql_string(status),
        _sql_string(rule.severity),
        str(int(failed_count)),
        _sql_string(observed_value),
        "CURRENT_TIMESTAMP()",
        _sql_string(rule.message),
        _sql_string(json.dumps({"rule": rule.rule, "columns": rule.columns}, sort_keys=True)),
    )
    return _insert_select(_table(environment, "quality"), columns, values)


def _insert_quarantine_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    rule: QualityIntent,
    source_sql: str,
    failed_condition: str,
) -> str:
    columns = (
        "run_id",
        "target_table",
        "rule_name",
        "error_reason",
        "record_payload",
        "record_ref",
        "reason",
        "quarantined_at_utc",
    )
    values = (
        _sql_string(run_id),
        _sql_string(snowflake_target_name(contract)),
        _sql_string(rule.name),
        _sql_string(rule.message or rule.rule),
        "TO_JSON(OBJECT_CONSTRUCT_KEEP_NULL(*))",
        "NULL",
        _sql_string(rule.message or rule.name),
        "CURRENT_TIMESTAMP()",
    )
    return (
        f"INSERT INTO {_table(environment, 'quarantine')} ({', '.join(quote_identifier(column) for column in columns)})\n"
        f"SELECT {', '.join(values)}\n"
        f"FROM (\n{source_sql}\n) AS _CF_SOURCE\n"
        f"WHERE {failed_condition}"
    )


def _insert_schema_change_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    schema_changes: dict[str, Any],
) -> tuple[str, ...]:
    commands: list[str] = []
    for change in _flatten_schema_changes(schema_changes):
        columns = (
            "run_id",
            "change_ts_utc",
            "target_table",
            "change_type",
            "column_name",
            "source_type",
            "target_type",
            "applied",
            "details_json",
            "payload_json",
            "changed_at_utc",
            "framework_version",
            "ctrl_schema_version",
        )
        values = (
            _sql_string(run_id),
            "CURRENT_TIMESTAMP()",
            _sql_string(snowflake_target_name(contract)),
            _sql_string(change.get("change_type")),
            _sql_string(change.get("column")),
            _sql_string(change.get("source_type")),
            _sql_string(change.get("target_type")),
            _sql_bool(change.get("applied")),
            _sql_json(change),
            _sql_json(schema_changes),
            "CURRENT_TIMESTAMP()",
            _sql_string("contractforge-snowflake"),
            "1",
        )
        commands.append(_insert_select(_table(environment, "schema_changes"), columns, values))
    return tuple(commands)


def _flatten_schema_changes(schema_changes: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    changes: list[dict[str, Any]] = []
    for key in ("added_columns", "removed_columns", "type_changes"):
        for item in schema_changes.get(key) or ():
            if isinstance(item, dict):
                changes.append(item)
    return tuple(changes)


def _insert_annotation_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    step: dict[str, Any],
    status: str,
    error_message: str | None,
) -> str:
    columns = (
        "run_id",
        "target_table",
        "annotation_scope",
        "annotation_type",
        "column_name",
        "key",
        "value",
        "status",
        "error_message",
        "applied_sql",
        "annotation_ts_utc",
        "annotation_date",
        "framework_version",
        "ctrl_schema_version",
    )
    values = (
        _sql_string(run_id),
        _sql_string(snowflake_target_name(contract)),
        _sql_string(step.get("scope")),
        _sql_string(step.get("annotation_type")),
        _sql_string(step.get("column_name")),
        _sql_string(step.get("key")),
        _sql_string(redact_text(str(step.get("value"))) if step.get("value") is not None else None),
        _sql_string(status),
        _sql_string(redact_text(error_message) if error_message else None),
        _sql_string(redact_text(str(step.get("sql"))) if step.get("sql") is not None else None),
        "CURRENT_TIMESTAMP()",
        "CURRENT_DATE()",
        _sql_string("contractforge-snowflake"),
        "1",
    )
    return _insert_select(_table(environment, "annotations"), columns, values)


def _insert_access_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    step: dict[str, Any],
    status: str,
    error_message: str | None,
) -> str:
    columns = (
        "access_run_id",
        "run_id",
        "target_table",
        "action",
        "access_type",
        "principal",
        "privilege",
        "column_name",
        "function_name",
        "object_name",
        "status",
        "error_message",
        "applied_sql",
        "previous_value",
        "new_value",
        "mode",
        "drift_policy",
        "revoke_unmanaged",
        "access_ts_utc",
        "access_date",
        "payload_json",
        "applied_at_utc",
        "framework_version",
        "ctrl_schema_version",
    )
    values = (
        _sql_string(redact_text(f"{run_id}:{step.get('action')}:{step.get('principal') or step.get('column_name') or step.get('access_type')}")),
        _sql_string(run_id),
        _sql_string(snowflake_target_name(contract)),
        _sql_string(step.get("action")),
        _sql_string(step.get("access_type")),
        _sql_redacted(step.get("principal")),
        _sql_redacted(step.get("privilege")),
        _sql_redacted(step.get("column_name")),
        _sql_redacted(step.get("function_name")),
        _sql_redacted(step.get("object_name")),
        _sql_string(status),
        _sql_string(redact_text(error_message) if error_message else None),
        _sql_redacted(step.get("sql")),
        _sql_redacted(step.get("previous_value")),
        _sql_redacted(step.get("new_value")),
        _sql_redacted(step.get("mode")),
        _sql_redacted(step.get("drift_policy")),
        _sql_bool(step.get("revoke_unmanaged")),
        "CURRENT_TIMESTAMP()",
        "CURRENT_DATE()",
        _sql_string(redact_text(json.dumps(step, sort_keys=True))),
        "CURRENT_TIMESTAMP()",
        _sql_string("contractforge-snowflake"),
        "1",
    )
    return _insert_select(_table(environment, "access"), columns, values)


def _insert_operations_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    payload: dict[str, Any],
    status: str,
) -> str:
    columns = (
        "run_id",
        "target_table",
        "criticality",
        "expected_frequency",
        "freshness_sla_minutes",
        "alert_on_failure",
        "alert_on_quality_fail",
        "runbook_url",
        "ownership_json",
        "owners_json",
        "groups_json",
        "tags_json",
        "status",
        "recorded_at_utc",
        "framework_version",
        "ctrl_schema_version",
    )
    values = (
        _sql_string(run_id),
        _sql_string(snowflake_target_name(contract)),
        _sql_string(payload.get("criticality")),
        _sql_string(payload.get("expected_frequency")),
        _sql_int(payload.get("freshness_sla_minutes")),
        _sql_bool(payload.get("alert_on_failure")),
        _sql_bool(payload.get("alert_on_quality_fail")),
        _sql_string(payload.get("runbook_url")),
        _sql_json(payload.get("ownership")),
        _sql_json(payload.get("owners")),
        _sql_json(payload.get("groups")),
        _sql_json(payload.get("tags")),
        _sql_string(status),
        "CURRENT_TIMESTAMP()",
        _sql_string("contractforge-snowflake"),
        "1",
    )
    return _insert_select(_table(environment, "operations"), columns, values)


def _insert_lineage_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    source_metadata: dict[str, Any],
    metrics: dict[str, Any],
) -> str:
    producer = _snowflake_extension(contract, "lineage_producer") or "contractforge-snowflake"
    namespace = _snowflake_extension(contract, "lineage_namespace") or "snowflake"
    source_name = _source_name(contract, source_metadata)
    event = _lineage_event(
        contract=contract,
        run_id=run_id,
        source_name=source_name,
        source_metadata=source_metadata,
        metrics=metrics,
        namespace=namespace,
        producer=producer,
    )
    columns = (
        "run_id",
        "event_time_utc",
        "event_type",
        "target_table",
        "source_table",
        "source_name",
        "namespace",
        "producer",
        "event_json",
    )
    values = (
        _sql_string(run_id),
        "CURRENT_TIMESTAMP()",
        _sql_string("COMPLETE"),
        _sql_string(snowflake_target_name(contract)),
        _sql_string(contract.source.location or contract.source.name),
        _sql_string(source_name),
        _sql_string(namespace),
        _sql_string(producer),
        _sql_string(redact_text(json.dumps(event, sort_keys=True, separators=(",", ":")))),
    )
    return _insert_select(_table(environment, "lineage"), columns, values)


def _insert_explain_sql(
    *,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    plan_text: str,
    explain_format: str,
) -> str:
    columns = (
        "run_id",
        "target_table",
        "source_table",
        "mode",
        "explain_format",
        "plan_text",
        "captured_at_utc",
    )
    values = (
        _sql_string(run_id),
        _sql_string(snowflake_target_name(contract)),
        _sql_string(contract.source.location or contract.source.name),
        _sql_string(contract.write.mode),
        _sql_string(explain_format.upper()),
        _sql_string(redact_text(plan_text)[:32000]),
        "CURRENT_TIMESTAMP()",
    )
    return _insert_select(_table(environment, "explain"), columns, values)


def _lineage_event(
    *,
    contract: SemanticContract,
    run_id: str,
    source_name: str,
    source_metadata: dict[str, Any],
    metrics: dict[str, Any],
    namespace: str,
    producer: str,
) -> dict[str, Any]:
    return {
        "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
        "eventType": "COMPLETE",
        "producer": producer,
        "run": {
            "runId": run_id,
            "facets": {
                "snowflake": {
                    "queryIds": metrics.get("query_ids") or [],
                    "writeQueryId": metrics.get("write_query_id"),
                    "warehouse": (metrics.get("snowflake") or {}).get("warehouse") if isinstance(metrics.get("snowflake"), dict) else None,
                }
            },
        },
        "job": {
            "namespace": namespace,
            "name": snowflake_target_name(contract),
        },
        "inputs": [
            {
                "namespace": namespace,
                "name": source_name,
                "facets": {"contractforgeSource": source_metadata},
            }
        ],
        "outputs": [
            {
                "namespace": namespace,
                "name": snowflake_target_name(contract),
                "facets": {
                    "dataQualityMetrics": {"rowCount": metrics.get("rows_written")},
                    "contractforge": {
                        "mode": contract.write.mode,
                        "qualityStatus": metrics.get("quality_status"),
                    },
                },
            }
        ],
    }


def _source_name(contract: SemanticContract, source_metadata: dict[str, Any]) -> str:
    for key in ("table", "stage", "query"):
        value = source_metadata.get(key)
        if value not in (None, ""):
            return str(value)
    return str(contract.source.location or contract.source.name or contract.source.kind)


def _snowflake_extension(contract: SemanticContract, key: str) -> str | None:
    snowflake = snowflake_extensions(contract)
    value = snowflake.get(key)
    return str(value) if value not in (None, "") else None


def _insert_select(table: str, columns: tuple[str, ...], values: tuple[str, ...]) -> str:
    return f"INSERT INTO {table} ({', '.join(quote_identifier(column) for column in columns)})\nSELECT {', '.join(values)}"


def _table(environment: SnowflakeEnvironment, table_key: str) -> str:
    table = EVIDENCE_TABLES[table_key]
    return ".".join(quote_identifier(part) for part in (_database(environment), _schema(environment), table))


def _database(environment: SnowflakeEnvironment) -> str:
    return environment.evidence_database or "CONTRACTFORGE"


def _schema(environment: SnowflakeEnvironment) -> str:
    return environment.evidence_schema or "CF_EVIDENCE"


def _split_statements(sql: str) -> tuple[str, ...]:
    return tuple(statement.strip() for statement in sql.split(";") if statement.strip())


def _execute(session: Any, command: str) -> None:
    execute(session, command)


def _sql_string(value: object | None) -> str:
    return sql_string(value)


def _sql_redacted(value: object | None) -> str:
    return _sql_string(redact_text(str(value)) if value is not None else None)


def _sql_json(value: object) -> str:
    return _sql_string(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _sql_bool(value: object) -> str:
    return "TRUE" if bool(value) else "FALSE"


def _sql_int(value: object) -> str:
    return "NULL" if value is None else str(int(value))


__all__ = [
    "SnowflakeEvidenceResult",
    "bootstrap_evidence_tables",
    "record_annotation_evidence",
    "record_access_evidence",
    "record_error_evidence",
    "record_explain_evidence",
    "record_lineage_evidence",
    "record_operations_evidence",
    "record_quality_evidence",
    "record_quarantine_evidence",
    "record_schema_change_evidence",
    "record_run_evidence",
]
