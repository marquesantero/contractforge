"""Control-table retention planning for Databricks evidence tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.sql import quote_identifier, quote_table_name


@dataclass(frozen=True)
class ControlRetentionTarget:
    key: str
    table: str
    age_expression: str
    description: str


CONTROL_RETENTION_TARGETS: tuple[ControlRetentionTarget, ...] = (
    ControlRetentionTarget("runs", "ctrl_ingestion_runs", "run_date", "Run history"),
    ControlRetentionTarget("errors", "ctrl_ingestion_errors", "error_date", "Error stack traces"),
    ControlRetentionTarget("quality", "ctrl_ingestion_quality", "checked_at_utc", "Quality results"),
    ControlRetentionTarget("quarantine", "ctrl_ingestion_quarantine", "quarantined_at_utc", "Quarantine references"),
    ControlRetentionTarget("locks", "ctrl_ingestion_locks", "COALESCE(released_at_utc, expires_at_utc, acquired_at_utc)", "Expired or released locks"),
    ControlRetentionTarget("explain", "ctrl_ingestion_explain", "captured_at_utc", "Explain plans"),
    ControlRetentionTarget("lineage", "ctrl_ingestion_lineage", "event_time_utc", "Lineage events"),
    ControlRetentionTarget("schema_changes", "ctrl_ingestion_schema_changes", "change_ts_utc", "Schema changes"),
    ControlRetentionTarget("streams", "ctrl_ingestion_streams", "COALESCE(ended_at_utc, started_at_utc)", "Stream history"),
    ControlRetentionTarget("annotations", "ctrl_ingestion_annotations", "annotation_date", "Annotation audit"),
    ControlRetentionTarget("operations", "ctrl_ingestion_operations", "recorded_at_utc", "Operational audit"),
    ControlRetentionTarget("access", "ctrl_ingestion_access", "access_date", "Access audit"),
    ControlRetentionTarget("cost", "ctrl_ingestion_cost", "captured_at_utc", "Cost signals"),
)


def build_control_retention_plan(
    *,
    catalog: str = "main",
    schema: str = "ops",
    retention_days: int,
    vacuum: bool = False,
    vacuum_retention_hours: int = 168,
    targets: Iterable[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    if retention_days < 1:
        raise ValueError("retention_days must be greater than or equal to 1")
    if vacuum_retention_hours < 0:
        raise ValueError("vacuum_retention_hours must be greater than or equal to 0")
    requested = {str(target) for target in (targets or [])}
    known = {target.key for target in CONTROL_RETENTION_TARGETS}
    unknown = requested - known
    if unknown:
        raise ValueError(f"unknown ctrl retention targets: {sorted(unknown)}")
    plan = []
    for target in CONTROL_RETENTION_TARGETS:
        if requested and target.key not in requested:
            continue
        table = f"{catalog}.{schema}.{target.table}"
        predicate = _cutoff_predicate(target.age_expression, retention_days)
        commands = [f"DELETE FROM {quote_table_name(table)} WHERE {predicate}"]
        if vacuum:
            commands.append(f"VACUUM {quote_table_name(table)} RETAIN {int(vacuum_retention_hours)} HOURS")
        plan.append(
            {
                "target": target.key,
                "table": table,
                "description": target.description,
                "retention_days": retention_days,
                "predicate": predicate,
                "commands": commands,
            }
        )
    return tuple(plan)


def execute_control_retention_plan(runner: SqlRunner, plan: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    executed = []
    for item in plan:
        for command in item["commands"]:
            runner.sql(str(command))
            executed.append(str(command))
    return tuple(executed)


def _cutoff_predicate(age_expression: str, retention_days: int) -> str:
    expression = age_expression.strip()
    if expression.endswith("_date") and "(" not in expression:
        return f"{quote_identifier(expression)} < date_sub(current_date(), {int(retention_days)})"
    return f"{expression} < current_timestamp() - INTERVAL {int(retention_days)} DAYS"
