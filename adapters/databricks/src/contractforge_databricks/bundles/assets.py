"""Databricks Asset Bundle rendering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatabricksJobSpec:
    bundle_name: str
    job_name: str
    task_key: str
    notebook_path: str
    target: str = "dev"


def render_databricks_asset_bundle(spec: DatabricksJobSpec) -> str:
    _require_non_empty(spec.bundle_name, "bundle_name")
    _require_non_empty(spec.job_name, "job_name")
    _require_non_empty(spec.task_key, "task_key")
    _require_non_empty(spec.notebook_path, "notebook_path")
    return "\n".join(
        [
            "bundle:",
            f"  name: {spec.bundle_name}",
            "",
            "resources:",
            "  jobs:",
            f"    {spec.job_name}:",
            f"      name: {spec.job_name}",
            "      tasks:",
            f"        - task_key: {spec.task_key}",
            "          notebook_task:",
            f"            notebook_path: {spec.notebook_path}",
            "",
            "targets:",
            f"  {spec.target}:",
            "    mode: development",
            "",
        ]
    )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")

