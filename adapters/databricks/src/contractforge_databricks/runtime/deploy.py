"""Databricks Asset Bundle deployment helpers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from contractforge_databricks.bundles import render_databricks_project_bundle
from contractforge_databricks.cli_io import load_mapping, write_mapping

CommandRunner = Callable[[tuple[str, ...], Path], dict[str, Any]]
DEFAULT_CLI_TIMEOUT_SECONDS = 600
_CLI_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def deploy_databricks_project(
    project: str | Path,
    *,
    profile: str | None = None,
    target: str | None = None,
    run: bool = False,
    validate: bool = True,
    render_bundle: bool = False,
    force_render: bool = False,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Validate/deploy/run the Databricks Asset Bundle declared by a project."""

    project_path = Path(project)
    project_file = project_path / "project.yaml" if project_path.is_dir() else project_path
    project_root = project_file.parent
    bundle_file = _project_bundle_file(project_file, project_root)
    render_result = (
        render_databricks_project_bundle_file(project_file, bundle_file, target=target or "dev", force=force_render)
        if render_bundle
        else None
    )
    result = deploy_databricks_bundle(
        bundle_file,
        profile=profile,
        target=target,
        run=run,
        validate=validate,
        command_runner=command_runner,
    )
    if render_result:
        result["render"] = render_result
    return result


def deploy_databricks_bundle(
    bundle: str | Path,
    *,
    profile: str | None = None,
    target: str | None = None,
    run: bool = False,
    validate: bool = True,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Validate/deploy/run a Databricks Asset Bundle using the Databricks CLI."""

    bundle_path = Path(bundle)
    bundle_root = bundle_path.parent if bundle_path.is_file() else bundle_path
    bundle_file = bundle_path if bundle_path.is_file() else bundle_root / "databricks.yml"
    payload = load_mapping(bundle_file)
    job_key = _single_job_key(payload)
    runner = command_runner or _run_databricks_cli
    steps = tuple(name for name in ("validate", "deploy", "run") if name != "validate" or validate)
    selected_steps = steps if run else tuple(name for name in steps if name != "run")
    results = [_execute_step(name, bundle_root, runner, profile=profile, target=target, job_key=job_key) for name in selected_steps]
    status = "SUCCESS" if all(item["returncode"] == 0 for item in results) else "FAILED"
    return {
        "status": status,
        "bundle_root": str(bundle_root),
        "bundle_file": str(bundle_file),
        "job_key": job_key,
        "profile": profile,
        "target": target,
        "steps": results,
    }


def render_databricks_project_bundle_file(
    project: str | Path,
    output: str | Path,
    *,
    target: str = "dev",
    force: bool = False,
) -> dict[str, Any]:
    """Render a Databricks Asset Bundle file from ``project.yaml`` metadata."""

    project_path = Path(project)
    project_file = project_path / "project.yaml" if project_path.is_dir() else project_path
    payload = load_mapping(project_file)
    bundle = render_databricks_project_bundle(payload, project_root=project_file.parent, target=target)
    output_path = Path(output)
    write_mapping(output_path, bundle, force=force)
    return {"status": "SUCCESS", "project": str(project_file), "bundle_file": str(output_path), "target": target}


def _execute_step(
    name: str,
    bundle_root: Path,
    runner: CommandRunner,
    *,
    profile: str | None,
    target: str | None,
    job_key: str,
) -> dict[str, Any]:
    command = _command(name, profile=profile, target=target, job_key=job_key)
    result = runner(command, bundle_root)
    if result["returncode"] != 0:
        raise RuntimeError(f"databricks bundle {name} failed: {result.get('stderr') or result.get('stdout')}")
    return {"step": name, **result}


def _command(name: str, *, profile: str | None, target: str | None, job_key: str) -> tuple[str, ...]:
    safe_job_key = _validated_cli_value(job_key, label="Databricks job key")
    builders = {
        "validate": lambda: ("databricks", *_profile(profile), "bundle", "validate", *_target(target), "--output", "json"),
        "deploy": lambda: ("databricks", *_profile(profile), "bundle", "deploy", *_target(target), "--output", "json"),
        "run": lambda: ("databricks", *_profile(profile), "bundle", "run", safe_job_key, *_target(target), "--output", "json"),
    }
    try:
        return builders[name]()
    except KeyError as exc:
        raise ValueError(f"unsupported Databricks deployment step: {name}") from exc


def _run_databricks_cli(command: tuple[str, ...], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
            timeout=DEFAULT_CLI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": list(command),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": f"Databricks CLI timed out after {DEFAULT_CLI_TIMEOUT_SECONDS} seconds",
            "json": None,
        }
    return {
        "command": list(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "json": _json_or_none(completed.stdout),
    }


def _project_bundle_file(project_path: Path, project_root: Path) -> Path:
    if project_path.name in {"databricks.yml", "databricks.yaml"}:
        return project_path
    payload = load_mapping(project_path)
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    databricks = validation.get("databricks") if isinstance(validation.get("databricks"), dict) else {}
    bundle = str(databricks.get("bundle") or "databricks.yml")
    return project_root / bundle


def _single_job_key(payload: dict[str, Any]) -> str:
    resources = payload.get("resources") if isinstance(payload.get("resources"), dict) else {}
    jobs = resources.get("jobs") if isinstance(resources.get("jobs"), dict) else {}
    keys = tuple(str(key) for key in jobs)
    if len(keys) != 1:
        raise ValueError("Databricks deploy run requires exactly one bundle job key")
    return keys[0]


def _profile(value: str | None) -> tuple[str, ...]:
    return ("--profile", _validated_cli_value(value, label="Databricks profile")) if value else ()


def _target(value: str | None) -> tuple[str, ...]:
    return ("--target", _validated_cli_value(value, label="Databricks target")) if value else ()


def _validated_cli_value(value: str, *, label: str) -> str:
    if not _CLI_VALUE_RE.fullmatch(value):
        raise ValueError(f"{label} must match {_CLI_VALUE_RE.pattern}")
    return value


def _json_or_none(value: str) -> Any | None:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None
