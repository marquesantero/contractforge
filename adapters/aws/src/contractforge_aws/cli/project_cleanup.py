"""AWS project cleanup planning.

The command in this module is intentionally non-destructive. It turns the same
project/environment inputs used by ``deploy-project`` into an explicit cleanup
plan operators can review and run themselves.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws.api import render_aws_contract
from contractforge_aws.cli.project_support import project_environment_path, project_execution_steps, step_contract_path
from contractforge_aws.cli.support import load_contract_input, load_environment_input, load_mapping
from contractforge_aws.rendering.names import glue_database_name


def add_cleanup_project_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    cleanup = subparsers.add_parser(
        "cleanup-project",
        help="Render a non-destructive cleanup plan for an AWS ContractForge project.",
    )
    cleanup.add_argument("project", type=Path)
    cleanup.add_argument("--environment", type=Path, help="Override the AWS environment file declared in project.yaml.")
    cleanup.add_argument("--environment-key", default="aws")


def handle_cleanup_project_command(args: argparse.Namespace) -> int | None:
    if args.command != "cleanup-project":
        return None
    payload = cleanup_project_payload(
        args.project,
        environment_path=args.environment,
        environment_key=args.environment_key,
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


def cleanup_project_payload(
    project_path: Path,
    *,
    environment_path: Path | None = None,
    environment_key: str = "aws",
) -> dict[str, Any]:
    project_root = project_path.parent
    project = load_mapping(project_path, label="project")
    resolved_environment_path = environment_path or project_environment_path(project, project_root, environment_key)
    environment = load_environment_input(resolved_environment_path, None)
    steps = [
        _cleanup_step(step, project_root=project_root, environment=environment, environment_key=environment_key)
        for step in project_execution_steps(project)
    ]
    return {
        "project": str(project_path),
        "environment": str(resolved_environment_path),
        "environment_key": environment_key,
        "mode": "plan",
        "destructive": False,
        "steps": steps,
        "shared_resources": _shared_cleanup_resources(environment, project),
        "notes": [
            "This command does not delete resources.",
            "Review the generated commands and remove only resources dedicated to this test/project.",
            "Glue databases may contain Iceberg tables and evidence history; dropping them is irreversible.",
        ],
    }


def _cleanup_step(step: dict[str, Any], *, project_root: Path, environment: dict, environment_key: str) -> dict[str, Any]:
    contract_path = project_root / step_contract_path(step, environment_key)
    contract, bundle_environment = load_contract_input(contract_path)
    effective_environment = environment or bundle_environment
    semantic = semantic_contract_from_mapping(contract)
    rendered = render_aws_contract(contract, environment=effective_environment).artifacts
    return {
        "name": str(step.get("name") or contract_path.stem),
        "contract": str(contract_path),
        "glue_job_names": _glue_job_names(rendered),
        "target_database": glue_database_name(semantic),
        "target_table": semantic.target.name,
        "cleanup_commands": _step_cleanup_commands(rendered),
    }


def _glue_job_names(artifacts: dict[str, object]) -> list[str]:
    names: list[str] = []
    for artifact_name, body in sorted(artifacts.items()):
        if not artifact_name.endswith(".glue_job_definition.json"):
            continue
        try:
            payload = json.loads(str(body))
        except json.JSONDecodeError:
            continue
        name = payload.get("Name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _step_cleanup_commands(artifacts: dict[str, object]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for job_name in _glue_job_names(artifacts):
        commands.append(
            {
                "resource": "aws_glue_job",
                "name": job_name,
                "command": ["aws", "glue", "delete-job", "--job-name", job_name],
            }
        )
    return commands


def _shared_cleanup_resources(environment: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    evidence_database = _evidence_database(environment)
    artifact_uri = _artifact_uri(environment)
    warehouse_uri = _warehouse_uri(environment)
    resources: dict[str, Any] = {
        "artifact_s3_uri": artifact_uri,
        "warehouse_s3_uri": warehouse_uri,
        "evidence_database": evidence_database,
        "commands": [],
        "external_resources": _external_cleanup_resources(project),
    }
    if artifact_uri:
        resources["commands"].append({"resource": "s3_artifact_prefix", "command": ["aws", "s3", "rm", artifact_uri, "--recursive"]})
    if warehouse_uri:
        resources["commands"].append({"resource": "s3_warehouse_prefix", "command": ["aws", "s3", "rm", warehouse_uri, "--recursive"]})
    if evidence_database:
        resources["commands"].append(
            {
                "resource": "glue_evidence_database",
                "name": evidence_database,
                "command": ["aws", "glue", "delete-database", "--name", evidence_database],
                "warning": "Delete only after dropping/archiving tables and S3 data owned by this project.",
            }
        )
    return resources


def _evidence_database(environment: dict[str, Any]) -> str | None:
    evidence = environment.get("evidence")
    if not isinstance(evidence, dict):
        return None
    value = evidence.get("database") or evidence.get("schema")
    return str(value) if value else None


def _artifact_uri(environment: dict[str, Any]) -> str | None:
    artifacts = environment.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    value = artifacts.get("uri") or artifacts.get("path")
    return str(value) if value else None


def _warehouse_uri(environment: dict[str, Any]) -> str | None:
    parameters = environment.get("parameters")
    aws = parameters.get("aws") if isinstance(parameters, dict) else None
    iceberg = aws.get("iceberg") if isinstance(aws, dict) else None
    value = iceberg.get("warehouse") if isinstance(iceberg, dict) else None
    return str(value) if value else None


def _external_cleanup_resources(project: dict[str, Any]) -> list[dict[str, Any]]:
    cleanup = project.get("cleanup")
    if not isinstance(cleanup, dict):
        return []
    resources = cleanup.get("external_resources")
    if not isinstance(resources, list):
        return []
    return [dict(item) for item in resources if isinstance(item, dict)]
