"""Render Databricks Asset Bundles from ContractForge project metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from contractforge_databricks.bundles.project_config import (
    databricks_deployment,
    databricks_scheduling,
    job_fields,
    mapping,
    required_text,
    runtime_environment,
    sequence,
    slug,
    text,
    validation_job_name,
    variable_parameter,
    variables,
)
from contractforge_databricks.cli_io import yaml_dump

_DEFAULT_TARGET = "dev"
_DEFAULT_CONTRACT_NOTEBOOK = "./notebooks/run_contractforge.py"
_DEFAULT_ENVIRONMENT_KEY = "contractforge_runtime"
_EXTRA_TASK_META_KEYS = {
    "base_parameters",
    "depends_on",
    "environment_key",
    "name",
    "notebook_path",
    "task_key",
}


def render_databricks_project_bundle(
    project: Mapping[str, Any],
    *,
    project_root: str | Path | None = None,
    target: str = _DEFAULT_TARGET,
) -> dict[str, Any]:
    """Render a Databricks Asset Bundle document from project-level metadata."""

    deployment = databricks_deployment(project)
    scheduling = databricks_scheduling(project)
    project_name = required_text(project.get("name"), "project.name")
    bundle_name = text(deployment.get("bundle_name")) or slug(project_name)
    job_key = text(deployment.get("job_key")) or slug(project_name)
    job_name = text(deployment.get("job_name")) or validation_job_name(project) or project_name
    variables_payload = variables(deployment)
    job = {
        "name": job_name,
        **job_fields(scheduling),
        **runtime_environment(deployment, variables_payload),
        "tasks": _tasks(project, deployment, scheduling, variables_payload),
    }
    bundle: dict[str, Any] = {
        "bundle": {"name": bundle_name},
        "resources": {"jobs": {job_key: job}},
        "targets": {target: {"default": True}},
    }
    workspace_root = text(deployment.get("workspace_root_path") or deployment.get("workspace_root"))
    if workspace_root:
        bundle["workspace"] = {"root_path": workspace_root}
    if variables_payload:
        bundle["variables"] = variables_payload
    return bundle


def render_databricks_project_bundle_yaml(
    project: Mapping[str, Any],
    *,
    project_root: str | Path | None = None,
    target: str = _DEFAULT_TARGET,
) -> str:
    """Render a Databricks Asset Bundle YAML document from project metadata."""

    return yaml_dump(render_databricks_project_bundle(project, project_root=project_root, target=target))


def _tasks(
    project: Mapping[str, Any],
    deployment: Mapping[str, Any],
    scheduling: Mapping[str, Any],
    variables: Mapping[str, Any],
) -> list[dict[str, Any]]:
    task_overrides = mapping(scheduling.get("tasks"))
    task_keys = _all_task_keys(project, scheduling, task_overrides)
    extra_tasks = _extra_tasks(scheduling, deployment, task_keys)
    return [
        *[task for task in extra_tasks if not task.get("depends_on")],
        *[
        _contract_task(step, deployment, task_overrides, task_keys, variables)
        for step in _execution_order(project)
        ],
        *[task for task in extra_tasks if task.get("depends_on")],
    ]


def _extra_tasks(
    scheduling: Mapping[str, Any],
    deployment: Mapping[str, Any],
    task_keys: Mapping[str, str],
) -> list[dict[str, Any]]:
    return [_extra_task(task, deployment, task_keys) for task in sequence(scheduling.get("extra_tasks")) if isinstance(task, Mapping)]


def _extra_task(task: Mapping[str, Any], deployment: Mapping[str, Any], task_keys: Mapping[str, str]) -> dict[str, Any]:
    task_key = required_text(task.get("task_key") or task.get("name"), "scheduling.databricks.extra_tasks[].task_key")
    environment_key = text(task.get("environment_key") or deployment.get("environment_key")) or _DEFAULT_ENVIRONMENT_KEY
    rendered = {
        "task_key": task_key,
        "environment_key": environment_key,
        **_task_dependencies(task, task_keys),
        **_extra_task_body(task),
    }
    return {key: value for key, value in rendered.items() if value not in ({}, None)}


def _extra_task_body(task: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(task.get("notebook_task"), Mapping):
        return {"notebook_task": dict(task["notebook_task"])}
    notebook_path = text(task.get("notebook_path"))
    if notebook_path:
        return {
            "notebook_task": {
                "notebook_path": notebook_path,
                "base_parameters": {str(key): str(value) for key, value in mapping(task.get("base_parameters")).items()},
            }
        }
    raw = {str(key): value for key, value in task.items() if key not in _EXTRA_TASK_META_KEYS}
    return raw


def _contract_task(
    step: Mapping[str, Any],
    deployment: Mapping[str, Any],
    task_overrides: Mapping[str, Any],
    task_keys: Mapping[str, str],
    variables: Mapping[str, Any],
) -> dict[str, Any]:
    name = required_text(step.get("name"), "execution_order[].name")
    override = mapping(task_overrides.get(name))
    contract = _databricks_contract(step)
    environment_key = text(override.get("environment_key") or deployment.get("environment_key")) or _DEFAULT_ENVIRONMENT_KEY
    notebook_path = text(override.get("notebook_path") or deployment.get("contract_notebook_path")) or _DEFAULT_CONTRACT_NOTEBOOK
    task = {
        "task_key": task_keys[name],
        "environment_key": environment_key,
        **_task_dependencies(step, task_keys),
        "notebook_task": {
            "notebook_path": notebook_path,
            "base_parameters": _base_parameters(contract, override, variables),
        },
    }
    return {key: value for key, value in task.items() if value not in ({}, None)}


def _base_parameters(contract: str, override: Mapping[str, Any], variables: Mapping[str, Any]) -> dict[str, str]:
    base = {
        **variable_parameter("bundle_root", variables),
        "contract": contract,
        **variable_parameter("evidence_catalog", variables),
        **variable_parameter("evidence_schema", variables),
    }
    extra = mapping(override.get("base_parameters"))
    return {**base, **{str(key): str(value) for key, value in extra.items()}}


def _task_dependencies(step: Mapping[str, Any], task_keys: Mapping[str, str]) -> dict[str, list[dict[str, str]]]:
    dependencies = [_dependency_task_key(name, task_keys) for name in sequence(step.get("depends_on"))]
    return {"depends_on": [{"task_key": key} for key in dependencies]} if dependencies else {}


def _dependency_task_key(name: Any, task_keys: Mapping[str, str]) -> str:
    value = required_text(name, "execution_order[].depends_on[]")
    return task_keys.get(value, value)


def _databricks_contract(step: Mapping[str, Any]) -> str:
    contracts = mapping(step.get("contracts"))
    value = text(contracts.get("databricks"))
    if not value:
        raise ValueError(f"execution_order entry {step.get('name')!r} must declare contracts.databricks")
    path = Path(value)
    return str(path.as_posix() if path.is_absolute() else path.as_posix())


def _all_task_keys(project: Mapping[str, Any], scheduling: Mapping[str, Any], task_overrides: Mapping[str, Any]) -> dict[str, str]:
    contract_keys = {
        name: text(mapping(task_overrides.get(name)).get("task_key") or step.get("task_key")) or slug(name)
        for step in _execution_order(project)
        for name in (required_text(step.get("name"), "execution_order[].name"),)
    }
    extra_keys = {
        required_text(task.get("name"), "scheduling.databricks.extra_tasks[].name"): required_text(
            task.get("task_key"), "scheduling.databricks.extra_tasks[].task_key"
        )
        for task in sequence(scheduling.get("extra_tasks"))
        if isinstance(task, Mapping) and task.get("name")
    }
    return {**contract_keys, **extra_keys}


def _execution_order(project: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    steps = project.get("execution_order")
    if not isinstance(steps, list) or not steps:
        raise ValueError("project.execution_order must be a non-empty list")
    invalid = [step for step in steps if not isinstance(step, Mapping)]
    if invalid:
        raise ValueError("project.execution_order entries must be objects")
    return tuple(steps)
