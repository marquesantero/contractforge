"""Control-table retention planning for Snowflake evidence tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from contractforge_snowflake.naming import quote_identifier, quote_multipart_identifier
from contractforge_snowflake.session_ops import execute


@dataclass(frozen=True)
class SnowflakeControlRetentionTarget:
    key: str
    table: str
    age_expression: str
    description: str


CONTROL_RETENTION_TARGETS: tuple[SnowflakeControlRetentionTarget, ...] = (
    SnowflakeControlRetentionTarget("runs", "ctrl_ingestion_runs", "run_date", "Run history"),
    SnowflakeControlRetentionTarget("errors", "ctrl_ingestion_errors", "error_date", "Error stack traces"),
    SnowflakeControlRetentionTarget("quality", "ctrl_ingestion_quality", "checked_at_utc", "Quality results"),
    SnowflakeControlRetentionTarget("quarantine", "ctrl_ingestion_quarantine", "quarantined_at_utc", "Quarantine references"),
    SnowflakeControlRetentionTarget("locks", "ctrl_ingestion_locks", "COALESCE(released_at_utc, expires_at_utc, acquired_at_utc)", "Expired or released locks"),
    SnowflakeControlRetentionTarget("explain", "ctrl_ingestion_explain", "captured_at_utc", "Explain plans"),
    SnowflakeControlRetentionTarget("lineage", "ctrl_ingestion_lineage", "event_time_utc", "Lineage events"),
    SnowflakeControlRetentionTarget("schema_changes", "ctrl_ingestion_schema_changes", "change_ts_utc", "Schema changes"),
    SnowflakeControlRetentionTarget("streams", "ctrl_ingestion_streams", "COALESCE(ended_at_utc, started_at_utc)", "Stream history"),
    SnowflakeControlRetentionTarget("annotations", "ctrl_ingestion_annotations", "annotation_date", "Annotation audit"),
    SnowflakeControlRetentionTarget("operations", "ctrl_ingestion_operations", "recorded_at_utc", "Operational audit"),
    SnowflakeControlRetentionTarget("access", "ctrl_ingestion_access", "access_date", "Access audit"),
    SnowflakeControlRetentionTarget("cost", "ctrl_ingestion_cost", "captured_at_utc", "Cost signals"),
    SnowflakeControlRetentionTarget("state", "ctrl_ingestion_state", "last_updated_at_utc", "State history"),
)


def build_control_retention_plan(
    *,
    database: str = "CONTRACTFORGE",
    schema: str = "CF_EVIDENCE",
    retention_days: int,
    targets: Iterable[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    if retention_days < 1:
        raise ValueError("retention_days must be greater than or equal to 1")
    requested = {str(target) for target in (targets or [])}
    known = {target.key for target in CONTROL_RETENTION_TARGETS}
    unknown = requested - known
    if unknown:
        raise ValueError(f"unknown ctrl retention targets: {sorted(unknown)}")
    plan = []
    for target in CONTROL_RETENTION_TARGETS:
        if requested and target.key not in requested:
            continue
        table = f"{database}.{schema}.{target.table}"
        predicate = _cutoff_predicate(target.age_expression, retention_days)
        plan.append(
            {
                "target": target.key,
                "table": table,
                "description": target.description,
                "retention_days": retention_days,
                "predicate": predicate,
                "commands": [f"DELETE FROM {quote_multipart_identifier(table)} WHERE {predicate}"],
            }
        )
    return tuple(plan)


def execute_control_retention_plan(session: Any, plan: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    executed = []
    for item in plan:
        for command in item["commands"]:
            execute(session, str(command))
            executed.append(str(command))
    return tuple(executed)


def _cutoff_predicate(age_expression: str, retention_days: int) -> str:
    expression = age_expression.strip()
    if expression.endswith("_date") and "(" not in expression:
        return f"{quote_identifier(expression)} < DATEADD(day, -{int(retention_days)}, CURRENT_DATE())"
    return f"{expression} < DATEADD(day, -{int(retention_days)}, CURRENT_TIMESTAMP())"
