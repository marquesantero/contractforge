"""Render Snowflake task graph deployment artifacts.

The task graph invokes the stable ContractForge Snowflake runtime procedure.
It never embeds source, transform, quality, or write-mode ingestion logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

from contractforge_core.project import parse_standard_cron, project_schedule_intent
from contractforge_snowflake.naming import quote_identifier, quote_multipart_identifier
from contractforge_snowflake.sql import sql_string
from contractforge_snowflake.values import mapping_view as _mapping
from contractforge_snowflake.values import text_bool as _bool


DEFAULT_TASK_DATABASE = "CONTRACTFORGE"
DEFAULT_TASK_SCHEMA = "CF_TASKS"
DEFAULT_RUNNER_PROCEDURE = "CONTRACTFORGE.CF_RUNTIME.RUN_CONTRACTFORGE_CONTRACT"


@dataclass(frozen=True)
class SnowflakeTaskGraphStep:
    name: str
    contract_artifact: str
    environment_artifact: str | None
    depends_on: tuple[str, ...] = ()


def render_project_task_graph(
    project: Mapping[str, Any],
    *,
    environment: Mapping[str, Any] | None,
    steps: Sequence[SnowflakeTaskGraphStep],
) -> str | None:
    """Render Snowflake task SQL for a project, when scheduling or dependencies exist."""

    if not steps or not _needs_task_graph(project, steps):
        return None
    settings = _settings(environment or {})
    schedule = project_schedule_intent(project)
    statement_blocks = [
        _render_task(
            step,
            settings=settings,
            schedule_clause=_schedule_clause(schedule) if schedule and not step.depends_on else None,
        )
        for step in steps
    ]
    return "\n\n".join(_header(settings) + statement_blocks) + "\n"


def _needs_task_graph(project: Mapping[str, Any], steps: Sequence[SnowflakeTaskGraphStep]) -> bool:
    return project_schedule_intent(project) is not None or any(step.depends_on for step in steps)


@dataclass(frozen=True)
class _TaskGraphSettings:
    database: str
    schema: str
    warehouse: str | None
    runner_procedure: str
    create_database: bool
    create_schema: bool


def _settings(environment: Mapping[str, Any]) -> _TaskGraphSettings:
    snowflake = _mapping(_mapping(environment.get("parameters")).get("snowflake"))
    return _TaskGraphSettings(
        database=_text(snowflake.get("task_database")) or DEFAULT_TASK_DATABASE,
        schema=_text(snowflake.get("task_schema")) or DEFAULT_TASK_SCHEMA,
        warehouse=_text(snowflake.get("warehouse")),
        runner_procedure=_text(snowflake.get("runner_procedure")) or DEFAULT_RUNNER_PROCEDURE,
        create_database=_bool(snowflake.get("task_create_database"), default=True),
        create_schema=_bool(snowflake.get("task_create_schema"), default=True),
    )


def _header(settings: _TaskGraphSettings) -> list[str]:
    lines = [
        "-- ContractForge Snowflake project deployment artifact.",
        "-- This SQL creates orchestration tasks only. Ingestion behavior remains inside the library runner.",
    ]
    if settings.create_database:
        lines.append(f"CREATE DATABASE IF NOT EXISTS {quote_identifier(settings.database)};")
    if settings.create_schema:
        lines.append(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(settings.database)}.{quote_identifier(settings.schema)};")
    return lines


def _render_task(step: SnowflakeTaskGraphStep, *, settings: _TaskGraphSettings, schedule_clause: str | None) -> str:
    clauses = [
        f"CREATE TASK IF NOT EXISTS {_task_name(settings, step.name)}",
        *_warehouse_clause(settings),
        *_dependency_clause(settings, step.depends_on),
        *([schedule_clause] if schedule_clause else []),
        "AS",
        f"  CALL {quote_multipart_identifier(settings.runner_procedure)}(",
        f"    {sql_string(step.contract_artifact)},",
        f"    {sql_string(step.environment_artifact)}",
        "  );",
    ]
    return "\n".join(clauses)


def _warehouse_clause(settings: _TaskGraphSettings) -> list[str]:
    return [f"  WAREHOUSE = {quote_identifier(settings.warehouse)}"] if settings.warehouse else []


def _dependency_clause(settings: _TaskGraphSettings, dependencies: tuple[str, ...]) -> list[str]:
    if not dependencies:
        return []
    joined = ", ".join(_task_name(settings, dependency) for dependency in dependencies)
    return [f"  AFTER {joined}"]


def _schedule_clause(schedule: Any) -> str:
    parse_standard_cron(schedule.cron)
    if "'" in schedule.timezone:
        raise ValueError("schedule.timezone cannot contain single quotes")
    enabled_note = "" if getattr(schedule, "enabled", True) else " -- declared disabled in project.yaml"
    return f"  SCHEDULE = 'USING CRON {schedule.cron} {schedule.timezone}'{enabled_note}"


def _task_name(settings: _TaskGraphSettings, name: str) -> str:
    return ".".join((quote_identifier(settings.database), quote_identifier(settings.schema), quote_identifier(name)))


def artifact_uri(*, artifact_name: str, artifact_root: str | None, stage: str | None, prefix: str | None) -> str | None:
    """Return the runtime URI for a published artifact, when a destination is known."""

    root = _artifact_root(artifact_root=artifact_root, stage=stage, prefix=prefix)
    if not root:
        return None
    return "/".join((root.rstrip("/"), str(PurePosixPath(artifact_name)).lstrip("/")))


def render_task_lifecycle_sql(
    *,
    environment: Mapping[str, Any] | None,
    task_names: Sequence[str],
    action: str,
) -> str:
    """Render explicit task lifecycle commands for resume, suspend, or execute."""

    settings = _settings(environment or {})
    normalized_action = action.strip().lower()
    if normalized_action not in {"resume", "suspend", "execute"}:
        raise ValueError("Snowflake task action must be resume, suspend, or execute")
    commands = tuple(_task_lifecycle_command(settings, task_name, normalized_action) for task_name in task_names)
    if not commands:
        raise ValueError("Snowflake task lifecycle requires at least one task name")
    return ";\n".join(commands) + ";\n"


def render_task_history_query(
    *,
    environment: Mapping[str, Any] | None,
    task_names: Sequence[str],
    limit: int = 20,
) -> str:
    """Render a bounded task history query for deployed ContractForge tasks."""

    settings = _settings(environment or {})
    if not task_names:
        raise ValueError("Snowflake task history query requires at least one task name")
    if limit < 1 or limit > 1000:
        raise ValueError("Snowflake task history limit must be between 1 and 1000")
    names = ", ".join(sql_string(task_name.upper()) for task_name in task_names)
    return "\n".join(
        (
            "SELECT NAME, STATE, QUERY_ID, SCHEDULED_TIME, COMPLETED_TIME, ERROR_CODE, ERROR_MESSAGE",
            f"FROM TABLE({quote_identifier(settings.database)}.INFORMATION_SCHEMA.TASK_HISTORY(",
            f"  RESULT_LIMIT => {int(limit)}",
            "))",
            f"WHERE UPPER(NAME) IN ({names})",
            "ORDER BY SCHEDULED_TIME DESC",
        )
    )


def _artifact_root(*, artifact_root: str | None, stage: str | None, prefix: str | None) -> str | None:
    explicit = _text(stage)
    if explicit:
        parts = [explicit.rstrip("/")]
        clean_prefix = _text(prefix)
        if clean_prefix:
            parts.append(clean_prefix.strip("/"))
        return "/".join(parts)
    root = _text(artifact_root)
    if not root:
        return None
    return root.removeprefix("snowflake://").rstrip("/")


def _task_lifecycle_command(settings: _TaskGraphSettings, task_name: str, action: str) -> str:
    task = _task_name(settings, task_name)
    if action == "resume":
        return f"ALTER TASK {task} RESUME"
    if action == "suspend":
        return f"ALTER TASK {task} SUSPEND"
    return f"EXECUTE TASK {task}"


def _text(value: Any) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None
