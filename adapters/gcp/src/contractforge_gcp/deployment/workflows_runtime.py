"""Optional Google Workflows runtime helpers for project deployment."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run_gcp_workflows_orchestration(
    *,
    workflow_manifest: dict[str, Any],
    workflow_source: Path,
    readback_plan: dict[str, Any] | None = None,
    cleanup_plan: dict[str, Any] | None = None,
    deploy: bool = False,
    run: bool = False,
    wait: bool = False,
    readback: bool = False,
    reset_data: bool = False,
    cleanup: bool = False,
    cleanup_data: bool = False,
    readback_location: str | None = None,
    service_account: str | None = None,
    execution_id: str | None = None,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Render or execute the adapter-owned Google Workflows command path."""

    workflow = _workflow(workflow_manifest)
    command_runner = runner or _run_command
    payload: dict[str, Any] = {
        "type": "workflows",
        "status": "CERTIFIED_FOR_STABLE_SURFACE",
        "certification_status": "CERTIFIED_FOR_STABLE_SURFACE",
        "workflow": workflow,
        "source": str(workflow_source),
        "commands": _commands(workflow, workflow_source, service_account=service_account),
        "promotion_blockers": [
            "Cloud Run Jobs, Composer DAGs and BigQuery scheduled-query runners are not certified by this Workflows command path.",
            "Automatic BigQuery type widening or mutation remains governed by the schema-policy gate.",
        ],
    }
    if readback_plan is not None:
        payload["commands"]["readback"] = _readback_commands(
            readback_plan,
            location_override=readback_location,
            execution_id=execution_id,
        )
    if cleanup_plan is not None:
        payload["commands"]["reset_data"] = _cleanup_data_commands(cleanup_plan, location_override=readback_location)
        payload["commands"]["cleanup_data"] = _cleanup_data_commands(cleanup_plan, location_override=readback_location)
    if not (deploy or run or wait or readback or reset_data or cleanup or cleanup_data):
        return payload

    if reset_data:
        if cleanup_plan is None:
            raise ValueError("--reset-orchestration-data requires the Workflows cleanup plan artifact")
        payload["reset_data"] = _run_cleanup_data(command_runner, cleanup_plan, location_override=readback_location)

    if deploy:
        payload["deployment"] = _run_json(command_runner, payload["commands"]["deploy"])

    current_execution_id = execution_id
    if run:
        execution = _run_json(command_runner, payload["commands"]["execute"])
        payload["execution"] = execution
        current_execution_id = current_execution_id or _execution_id(execution)

    if wait:
        if not current_execution_id:
            raise ValueError("--wait-orchestration requires --run-orchestration or --workflow-execution-id")
        wait_command = _replace_execution_id(payload["commands"]["wait_template"], current_execution_id)
        describe_command = _replace_execution_id(payload["commands"]["describe_template"], current_execution_id)
        payload["commands"]["wait"] = wait_command
        payload["commands"]["describe"] = describe_command
        payload["wait"] = _run_json(command_runner, wait_command)
        payload["describe"] = _run_json(command_runner, describe_command)
    if readback:
        if readback_plan is None:
            raise ValueError("--readback-orchestration requires the Workflows evidence readback artifact")
        payload["commands"]["readback"] = _readback_commands(
            readback_plan,
            location_override=readback_location,
            execution_id=current_execution_id,
        )
        payload["readback"] = _run_readback(
            command_runner,
            readback_plan,
            location_override=readback_location,
            execution_id=current_execution_id,
        )
    if cleanup:
        payload["cleanup"] = _run_cleanup(command_runner, payload["commands"]["cleanup"])
    if cleanup_data:
        if cleanup_plan is None:
            raise ValueError("--cleanup-orchestration-data requires the Workflows cleanup plan artifact")
        payload["cleanup_data"] = _run_cleanup_data(command_runner, cleanup_plan, location_override=readback_location)
    return payload


def _workflow(manifest: dict[str, Any]) -> dict[str, str]:
    workflow = manifest.get("workflow")
    if not isinstance(workflow, dict):
        raise ValueError("Workflows manifest must contain workflow metadata")
    required = ("name", "project_id", "location")
    missing = [key for key in required if not workflow.get(key)]
    if missing:
        raise ValueError(f"Workflows manifest missing workflow fields: {', '.join(missing)}")
    return {key: str(workflow[key]) for key in required}


def _commands(workflow: dict[str, str], workflow_source: Path, *, service_account: str | None) -> dict[str, list[str]]:
    deploy = [
        "gcloud",
        "workflows",
        "deploy",
        workflow["name"],
        f"--project={workflow['project_id']}",
        f"--location={workflow['location']}",
        f"--source={workflow_source}",
        "--format=json",
        "--quiet",
    ]
    if service_account:
        deploy.insert(-2, f"--service-account={service_account}")
    return {
        "deploy": deploy,
        "cleanup": [
            "gcloud",
            "workflows",
            "delete",
            workflow["name"],
            f"--project={workflow['project_id']}",
            f"--location={workflow['location']}",
            "--quiet",
        ],
        "execute": [
            "gcloud",
            "workflows",
            "execute",
            workflow["name"],
            f"--project={workflow['project_id']}",
            f"--location={workflow['location']}",
            "--format=json",
        ],
        "wait_template": [
            "gcloud",
            "workflows",
            "executions",
            "wait",
            "${execution_id}",
            f"--workflow={workflow['name']}",
            f"--project={workflow['project_id']}",
            f"--location={workflow['location']}",
            "--format=json",
        ],
        "describe_template": [
            "gcloud",
            "workflows",
            "executions",
            "describe",
            "${execution_id}",
            f"--workflow={workflow['name']}",
            f"--project={workflow['project_id']}",
            f"--location={workflow['location']}",
            "--format=json",
        ],
    }


def _readback_commands(
    readback_plan: dict[str, Any],
    *,
    location_override: str | None = None,
    execution_id: str | None = None,
) -> dict[str, list[str]]:
    project_id, location, queries = _readback_context(
        readback_plan,
        location_override=location_override,
        execution_id=execution_id,
    )
    return {
        name: [
            "bq",
            f"--project_id={project_id}",
            f"--location={location}",
            "--format=json",
            "query",
            "--use_legacy_sql=false",
            _bq_sql_argument(sql),
        ]
        for name, sql in queries.items()
    }


def _cleanup_data_commands(
    cleanup_plan: dict[str, Any],
    *,
    location_override: str | None = None,
) -> dict[str, list[str]]:
    project_id, location, queries = _query_plan_context(cleanup_plan, location_override=location_override)
    return {
        name: [
            "bq",
            f"--project_id={project_id}",
            f"--location={location}",
            "--format=json",
            "query",
            "--use_legacy_sql=false",
            _bq_sql_argument(sql),
        ]
        for name, sql in queries.items()
    }


def _replace_execution_id(command: Sequence[str], execution_id: str) -> list[str]:
    return [execution_id if item == "${execution_id}" else str(item) for item in command]


def _run_json(runner: CommandRunner, command: Sequence[str]) -> dict[str, Any]:
    completed = runner(tuple(command))
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"Command failed with exit code {completed.returncode}: {command[0]}")
    if not completed.stdout.strip():
        return {"command": list(command), "status": "SUCCEEDED", "raw": ""}
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"command": list(command), "status": "SUCCEEDED", "raw": completed.stdout.strip()}
    return parsed if isinstance(parsed, dict) else {"command": list(command), "result": parsed}


def _run_readback(
    runner: CommandRunner,
    readback_plan: dict[str, Any],
    *,
    location_override: str | None = None,
    execution_id: str | None = None,
) -> dict[str, Any]:
    commands = _readback_commands(readback_plan, location_override=location_override, execution_id=execution_id)
    results: dict[str, Any] = {}
    for name, command in commands.items():
        completed = runner(tuple(command))
        if completed.returncode != 0:
            raise RuntimeError(_command_error(completed, fallback=f"Readback query failed: {name}"))
        rows = _parse_json_rows(completed.stdout)
        results[name] = {
            "status": "SUCCEEDED",
            "row_count": len(rows),
            "rows": rows,
        }
    return {
        "status": "SUCCEEDED",
        "execution_scoped": bool(execution_id),
        "execution_id": execution_id,
        "query_count": len(results),
        "queries": results,
    }


def _run_cleanup_data(
    runner: CommandRunner,
    cleanup_plan: dict[str, Any],
    *,
    location_override: str | None = None,
) -> dict[str, Any]:
    commands = _cleanup_data_commands(cleanup_plan, location_override=location_override)
    results: dict[str, Any] = {}
    for name, command in commands.items():
        completed = runner(tuple(command))
        if completed.returncode != 0:
            raise RuntimeError(_command_error(completed, fallback=f"Cleanup query failed: {name}"))
        results[name] = {
            "status": "SUCCEEDED",
            "row_count": len(_parse_json_rows(completed.stdout)),
        }
    return {
        "status": "SUCCEEDED",
        "query_count": len(results),
        "queries": results,
    }


def _run_cleanup(runner: CommandRunner, command: Sequence[str]) -> dict[str, Any]:
    completed = runner(tuple(command))
    if completed.returncode == 0:
        return {
            "status": "SUCCEEDED",
            "command": list(command),
            "raw": _redact_cli_text((completed.stdout or completed.stderr).strip()),
        }
    error = _command_error(completed, fallback="Workflow cleanup failed")
    if _is_not_found_error(error):
        return {
            "status": "SKIPPED",
            "reason": "workflow_not_found",
            "command": list(command),
            "raw": error,
        }
    raise RuntimeError(error)


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    resolved = list(command)
    if resolved:
        resolved[0] = _resolve_executable(resolved[0])
    return subprocess.run(resolved, check=False, capture_output=True, text=True)


def _execution_id(payload: dict[str, Any]) -> str | None:
    for key in ("name", "execution", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.rstrip("/").split("/")[-1]
    return None


def _readback_context(
    readback_plan: dict[str, Any],
    *,
    location_override: str | None = None,
    execution_id: str | None = None,
) -> tuple[str, str, dict[str, str]]:
    evidence = readback_plan.get("evidence") if isinstance(readback_plan.get("evidence"), dict) else {}
    project_id = str(evidence.get("project_id") or readback_plan.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("Workflows evidence readback plan must include evidence.project_id")
    location = str(location_override or evidence.get("location") or "US").strip() or "US"
    raw_queries = readback_plan.get("queries")
    if execution_id:
        scoped_queries = readback_plan.get("execution_scoped_queries")
        if isinstance(scoped_queries, dict) and scoped_queries:
            raw_queries = scoped_queries
    if not isinstance(raw_queries, dict) or not raw_queries:
        raise ValueError("Workflows evidence readback plan must include queries")
    queries = {
        str(name): _bind_execution_id(str(sql), execution_id)
        for name, sql in raw_queries.items()
        if str(sql).strip()
    }
    if not queries:
        raise ValueError("Workflows evidence readback plan queries are empty")
    return project_id, location, queries


def _bind_execution_id(sql: str, execution_id: str | None) -> str:
    if not execution_id:
        return sql
    return sql.replace("${workflow_execution_id_sql}", _sql_string(execution_id))


def _query_plan_context(
    plan: dict[str, Any],
    *,
    location_override: str | None = None,
) -> tuple[str, str, dict[str, str]]:
    evidence = plan.get("evidence") if isinstance(plan.get("evidence"), dict) else {}
    project_id = str(evidence.get("project_id") or plan.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("Workflows cleanup plan must include evidence.project_id")
    location = str(location_override or evidence.get("location") or "US").strip() or "US"
    raw_queries = plan.get("queries")
    if not isinstance(raw_queries, dict) or not raw_queries:
        raise ValueError("Workflows cleanup plan must include queries")
    queries = {str(name): str(sql) for name, sql in raw_queries.items() if str(sql).strip()}
    if not queries:
        raise ValueError("Workflows cleanup plan queries are empty")
    return project_id, location, queries


def _parse_json_rows(value: str) -> list[dict[str, Any]]:
    if not value.strip():
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return [{"raw": value.strip()}]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return [{"result": payload}]


def _resolve_executable(executable: str) -> str:
    resolved = shutil.which(executable)
    return resolved or executable


def _command_error(completed: subprocess.CompletedProcess[str], *, fallback: str) -> str:
    return _redact_cli_text((completed.stderr or completed.stdout or fallback).strip())


def _redact_cli_text(value: str) -> str:
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted-email>", value)


def _is_not_found_error(value: str) -> bool:
    normalized = value.lower()
    return "not_found" in normalized or "not found" in normalized or "does not exist" in normalized


def _bq_sql_argument(sql: str) -> str:
    return " ".join(line.strip() for line in sql.splitlines() if line.strip())


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
