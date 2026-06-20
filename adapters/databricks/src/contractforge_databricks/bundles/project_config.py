"""Configuration helpers for Databricks project bundle rendering."""

from __future__ import annotations

import re
from typing import Any, Mapping

from contractforge_core.project import adapter_scheduling, quartz_cron_expression

_JOB_FIELD_BUILDERS = {
    "email_notifications": lambda value: value,
    "max_concurrent_runs": lambda value: int(value),
    "notification_settings": lambda value: value,
    "queue": lambda value: {"enabled": bool(value)} if isinstance(value, bool) else value,
    "schedule": lambda value: databricks_schedule(mapping(value)),
    "tags": lambda value: value,
    "timeout_seconds": lambda value: int(value),
    "webhook_notifications": lambda value: value,
}


def runtime_environment(deployment: Mapping[str, Any], variables: Mapping[str, Any]) -> dict[str, Any]:
    environment = mapping(deployment.get("runtime_environment"))
    enabled = environment.get("enabled", True)
    if not enabled:
        return {}
    dependency_values = dependencies(environment, variables)
    if not dependency_values:
        return {}
    return {
        "environments": [
            {
                "environment_key": text(deployment.get("environment_key")) or "contractforge_runtime",
                "spec": {
                    "environment_version": str(environment.get("environment_version") or "2"),
                    "dependencies": dependency_values,
                },
            }
        ]
    }


def dependencies(environment: Mapping[str, Any], variables: Mapping[str, Any]) -> list[str]:
    configured = [str(value) for value in sequence(environment.get("dependencies"))]
    wheel_vars = [f"${{var.{name}}}" for name in ("core_wheel_path", "databricks_wheel_path") if name in variables]
    return configured or wheel_vars


def job_fields(scheduling: Mapping[str, Any]) -> dict[str, Any]:
    fields = mapping(scheduling.get("job"))
    direct = {key: scheduling[key] for key in ("max_concurrent_runs", "queue", "schedule", "tags") if key in scheduling}
    configured = {**direct, **fields}
    return {
        key: _JOB_FIELD_BUILDERS[key](value)
        for key, value in configured.items()
        if key in _JOB_FIELD_BUILDERS and value is not None
    }


def databricks_schedule(schedule: Mapping[str, Any]) -> dict[str, Any]:
    cron = schedule.get("quartz_cron_expression") or _quartz_from_standard(schedule.get("cron"))
    if not cron:
        raise ValueError("schedule.cron is required for Databricks project scheduling")
    return {
        "quartz_cron_expression": str(cron),
        "timezone_id": str(schedule.get("timezone_id") or schedule.get("timezone") or "UTC"),
        "pause_status": str(schedule.get("pause_status") or _pause_status(schedule)),
    }


def variables(deployment: Mapping[str, Any]) -> dict[str, Any]:
    raw = mapping(deployment.get("variables"))
    defaults = {
        key: deployment[key]
        for key in ("bundle_root", "core_wheel_path", "databricks_wheel_path", "evidence_catalog", "evidence_schema")
        if key in deployment
    }
    values = {**defaults, **raw}
    return {str(key): value if isinstance(value, Mapping) else {"default": str(value)} for key, value in values.items()}


def variable_parameter(name: str, variables: Mapping[str, Any]) -> dict[str, str]:
    return {name: f"${{var.{name}}}"} if name in variables else {}


def databricks_deployment(project: Mapping[str, Any]) -> Mapping[str, Any]:
    deployment = mapping(project.get("deployment"))
    validation = mapping(project.get("validation"))
    return {**mapping(validation.get("databricks")), **mapping(deployment.get("databricks"))}


def databricks_scheduling(project: Mapping[str, Any]) -> Mapping[str, Any]:
    return adapter_scheduling(project, "databricks")


def validation_job_name(project: Mapping[str, Any]) -> str | None:
    validation = mapping(project.get("validation"))
    databricks = mapping(validation.get("databricks"))
    return text(databricks.get("job_name"))


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sequence(value: Any) -> tuple[Any, ...]:
    return tuple(value) if isinstance(value, list) else ()


def required_text(value: Any, field_name: str) -> str:
    value_text = text(value)
    if not value_text:
        raise ValueError(f"{field_name} must not be empty")
    return value_text


def text(value: Any) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None


def slug(value: str) -> str:
    rendered = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_").lower()
    return rendered or "contractforge_project"


def _quartz_from_standard(value: Any) -> str:
    return quartz_cron_expression(str(value)) if value is not None and str(value).strip() else ""


def _pause_status(schedule: Mapping[str, Any]) -> str:
    if schedule.get("paused", False) or schedule.get("enabled") is False:
        return "PAUSED"
    return "UNPAUSED"
