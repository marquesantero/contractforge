"""Shared helpers for AWS project-level CLI commands."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from contractforge_aws.api import plan_aws_contract, render_aws_contract
from contractforge_aws.runtime import AthenaSqlRunner, audit_evidence_tables


def project_environment_path(project: dict, project_root: Path, environment_key: str) -> Path:
    environments = project.get("environments")
    if not isinstance(environments, dict) or environment_key not in environments:
        raise ValueError(f"project.environments must declare {environment_key!r}")
    return project_root / str(environments[environment_key])


def project_execution_steps(project: dict) -> list[dict]:
    steps = project.get("execution_order")
    if not isinstance(steps, list) or not steps:
        raise ValueError("project.execution_order must be a non-empty list")
    if not all(isinstance(step, dict) for step in steps):
        raise ValueError("project.execution_order entries must be objects")
    return steps


def step_contract_path(step: dict, environment_key: str) -> str:
    contracts = step.get("contracts")
    if not isinstance(contracts, dict) or environment_key not in contracts:
        name = step.get("name") or "<unnamed>"
        raise ValueError(f"project step {name!r} must declare contracts.{environment_key}")
    return str(contracts[environment_key])


def deployment_payload(deployment, *, summary_only: bool = False) -> dict[str, object]:
    payload = asdict(deployment)
    artifacts = [asdict(artifact) for artifact in deployment.artifacts]
    payload["artifact_count"] = len(artifacts)
    payload["artifact_bytes_written"] = sum(int(artifact.get("bytes_written") or 0) for artifact in artifacts)
    if summary_only:
        payload.pop("artifacts", None)
        return payload
    payload["artifacts"] = artifacts
    return payload


def dry_run_step_payload(
    step: dict,
    *,
    contract_path: Path,
    contract: dict,
    environment: dict | None,
    summary_only: bool,
) -> dict[str, object]:
    planning = plan_aws_contract(contract, environment=environment)
    artifacts = render_aws_contract(contract, environment=environment).artifacts
    compile_report = python_compile_report(artifacts)
    _raise_for_compile_errors(compile_report)
    payload: dict[str, object] = {
        "name": str(step.get("name") or contract_path.stem),
        "contract": str(contract_path),
        "expected_result": str(step.get("expected_result") or "succeeded"),
        "planning_status": planning.status,
        "warning_codes": [warning.code for warning in planning.warnings],
        "blocker_codes": [blocker.code for blocker in planning.blockers],
        "artifact_count": len(artifacts),
        "job_name": glue_job_name(artifacts),
        "runnable": any(name.endswith(".glue_job.py") for name in artifacts),
        "python_compile_status": compile_report["status"],
        "python_artifacts_compiled": compile_report["compiled"],
    }
    if not summary_only:
        payload["artifacts"] = sorted(artifacts)
    return payload


def glue_job_name(artifacts: dict[str, object]) -> str | None:
    for name, body in sorted(artifacts.items()):
        if name.endswith(".glue_job_definition.json"):
            payload = json.loads(str(body))
            return str(payload.get("Name") or "").strip() or None
    return None


def run_project_evidence_audit(
    environment: dict | None,
    *,
    athena_output_location: str,
    athena_workgroup: str | None,
    poll_interval_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    database = project_evidence_database(environment)
    runner = AthenaSqlRunner(
        database=database,
        output_location=athena_output_location,
        workgroup=athena_workgroup,
        wait=True,
        poll_interval_seconds=poll_interval_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    return asdict(audit_evidence_tables(runner=runner, database=database))


def project_evidence_database(environment: dict | None) -> str:
    evidence = environment.get("evidence") if isinstance(environment, dict) else None
    if isinstance(evidence, dict) and evidence.get("database"):
        return str(evidence["database"])
    return "contractforge_ops"


def python_compile_report(artifacts: dict[str, object]) -> dict[str, object]:
    errors: list[dict[str, str]] = []
    compiled = 0
    for name, body in artifacts.items():
        if not name.endswith(".py"):
            continue
        compiled += 1
        try:
            compile(str(body), name, "exec")
        except SyntaxError as exc:
            errors.append({"artifact": name, "error": f"{exc.msg} at line {exc.lineno}"})
    return {"status": "PASS" if not errors else "FAIL", "compiled": compiled, "errors": errors}


def _raise_for_compile_errors(report: dict[str, object]) -> None:
    errors = report.get("errors")
    if not errors:
        return
    first = errors[0] if isinstance(errors, list) else {}
    artifact = first.get("artifact", "<unknown>") if isinstance(first, dict) else "<unknown>"
    error = first.get("error", "syntax error") if isinstance(first, dict) else "syntax error"
    raise ValueError(f"generated Python artifact {artifact!r} did not compile: {error}")
