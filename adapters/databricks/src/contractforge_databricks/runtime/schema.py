"""Runtime schema setup and schema-change evidence for Databricks."""

from __future__ import annotations

from typing import Any

from contractforge_core.runtime import PreparedInput
from contractforge_core.schema import compare_schema, validate_schema_diff
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.evidence import EvidenceWriter, render_schema_change_log_insert_sqls
from contractforge_databricks.execution import SqlRunner, execute_table_setup
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.schema import render_add_columns_sql, render_type_widening_sql


def setup_and_sync_schema(
    *,
    runner: SqlRunner,
    evidence: EvidenceWriter,
    contract: SemanticContract,
    prepared: PreparedInput,
    run_id: str,
    ensure_table: bool,
    target_schema: dict[str, str] | None,
) -> dict[str, Any]:
    """Apply Databricks schema policy using prepared-source schema evidence."""

    if not prepared.source_schema:
        return {}

    target = target_full_name(contract)
    if ensure_table:
        execute_table_setup(runner=runner, contract=contract, columns=prepared.source_schema)

    if target_schema is None:
        return {"status": "new_or_unknown", "source_schema": dict(prepared.source_schema)}

    allow_type_widening = bool(databricks_extensions(contract).get("allow_type_widening"))
    diff = compare_schema(
        prepared.source_schema,
        target_schema,
        allow_type_widening=allow_type_widening,
    )
    validate_schema_diff(diff, contract.write.schema_policy)
    changes = diff.as_dict()
    _apply_schema_sync_sql(runner, target, prepared.source_schema, diff)
    _mark_applied_schema_changes(changes)
    _write_schema_change_logs(evidence, run_id, target, changes, prepared.source_schema)
    return changes


def preview_schema_changes(
    *,
    contract: SemanticContract,
    prepared: PreparedInput,
    target_schema: dict[str, str] | None,
) -> dict[str, Any]:
    """Validate and describe schema changes without running Databricks DDL."""

    if not prepared.source_schema:
        return {}
    if target_schema is None:
        return {"status": "new_or_unknown", "source_schema": dict(prepared.source_schema)}
    diff = compare_schema(
        prepared.source_schema,
        target_schema,
        allow_type_widening=bool(databricks_extensions(contract).get("allow_type_widening")),
    )
    validate_schema_diff(diff, contract.write.schema_policy)
    return diff.as_dict()


def _apply_schema_sync_sql(runner: SqlRunner, target: str, source_schema: dict[str, str], diff: Any) -> None:
    for statement in (
        render_add_columns_sql(target_table=target, source_schema=source_schema, diff=diff),
        render_type_widening_sql(target_table=target, diff=diff),
    ):
        for part in statement.split(";"):
            sql = part.strip()
            if sql and not sql.startswith("--"):
                runner.sql(sql)


def _write_schema_change_logs(
    evidence: EvidenceWriter,
    run_id: str,
    target: str,
    changes: dict[str, Any],
    source_schema: dict[str, str],
) -> None:
    for statement in render_schema_change_log_insert_sqls(
        run_id=run_id,
        target_table=target,
        schema_changes=changes,
        source_schema=source_schema,
        catalog=evidence.catalog,
        schema=evidence.schema,
    ):
        evidence.runner.sql(statement)


def _mark_applied_schema_changes(changes: dict[str, Any]) -> None:
    for change in changes.get("type_changes") or ():
        if change.get("allowed"):
            change["applied"] = True
