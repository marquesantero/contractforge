"""Databricks Asset Bundle rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class DatabricksNotebookTaskSpec:
    task_key: str
    notebook_path: str
    base_parameters: Mapping[str, str] | None = None
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatabricksJobSpec:
    bundle_name: str
    job_name: str
    task_key: str
    notebook_path: str
    target: str = "dev"
    pre_tasks: tuple[DatabricksNotebookTaskSpec, ...] = ()


def render_databricks_asset_bundle(spec: DatabricksJobSpec) -> str:
    _require_non_empty(spec.bundle_name, "bundle_name")
    _require_non_empty(spec.job_name, "job_name")
    _require_non_empty(spec.task_key, "task_key")
    _require_non_empty(spec.notebook_path, "notebook_path")
    for task in spec.pre_tasks:
        _require_non_empty(task.task_key, "pre_tasks.task_key")
        _require_non_empty(task.notebook_path, "pre_tasks.notebook_path")
    main_depends_on = tuple(task.task_key for task in spec.pre_tasks)
    lines = [
        "bundle:",
        f"  name: {spec.bundle_name}",
        "",
        "resources:",
        "  jobs:",
        f"    {spec.job_name}:",
        f"      name: {spec.job_name}",
        "      tasks:",
    ]
    for task in spec.pre_tasks:
        lines.extend(_task_lines(task, indent="        "))
    lines.extend(
        _task_lines(
            DatabricksNotebookTaskSpec(
                task_key=spec.task_key,
                notebook_path=spec.notebook_path,
                depends_on=main_depends_on,
            ),
            indent="        ",
        )
    )
    lines.extend(
        [
            "",
            "targets:",
            f"  {spec.target}:",
            "    mode: development",
            "",
        ]
    )
    return "\n".join(lines)


def _task_lines(task: DatabricksNotebookTaskSpec, *, indent: str) -> list[str]:
    lines = [f"{indent}- task_key: {task.task_key}"]
    if task.depends_on:
        lines.append(f"{indent}  depends_on:")
        for dependency in task.depends_on:
            lines.append(f"{indent}    - task_key: {dependency}")
    lines.extend(
        [
            f"{indent}  notebook_task:",
            f"{indent}    notebook_path: {task.notebook_path}",
        ]
    )
    if task.base_parameters:
        lines.append(f"{indent}    base_parameters:")
        for key in sorted(task.base_parameters):
            lines.append(f"{indent}      {key}: {task.base_parameters[key]}")
    return lines


def _require_non_empty(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
