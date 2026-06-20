"""Cost evidence reconciliation for AWS Step Functions project runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from contractforge_aws.cli.project_cost import record_project_step_cost_evidence
from contractforge_aws.cli.project_support import project_execution_steps, step_contract_path
from contractforge_aws.cli.support import load_contract_input


def record_orchestration_cost_evidence(
    project: Mapping[str, Any],
    project_root: Path,
    *,
    environment_key: str,
    environment: dict | None,
    orchestration: Mapping[str, Any],
    athena_output_location: str,
    athena_workgroup: str | None,
    poll_interval_seconds: float,
    max_wait_seconds: float,
) -> list[dict[str, object]]:
    runs_by_job = _runs_by_job(orchestration)
    jobs = orchestration.get("jobs") if isinstance(orchestration.get("jobs"), Mapping) else {}
    results: list[dict[str, object]] = []
    for step in project_execution_steps(dict(project)):
        name = str(step.get("name") or "")
        job_name = str(jobs.get(name) or "")
        run_id = runs_by_job.get(job_name)
        if not run_id:
            results.append({"step": name, "job_name": job_name, "status": "NO_STEPFUNCTIONS_RUN_OUTPUT"})
            continue
        contract, _bundle_environment = load_contract_input(project_root / step_contract_path(step, environment_key))
        result = record_project_step_cost_evidence(
            environment,
            contract,
            job_name=job_name,
            run_id=run_id,
            athena_output_location=athena_output_location,
            athena_workgroup=athena_workgroup,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
        )
        results.append({"step": name, **result})
    return results


def _runs_by_job(orchestration: Mapping[str, Any]) -> dict[str, str]:
    wait = orchestration.get("wait")
    output = wait.get("output") if isinstance(wait, Mapping) else None
    if not output:
        return {}
    try:
        payload = json.loads(str(output))
    except json.JSONDecodeError:
        return {}
    runs: dict[str, str] = {}
    _collect_runs(payload, runs)
    return runs


def _collect_runs(value: Any, runs: dict[str, str]) -> None:
    if isinstance(value, Mapping):
        job_name = value.get("JobName")
        run_id = value.get("JobRunId") or value.get("Id")
        if job_name and run_id:
            runs[str(job_name)] = str(run_id)
        for item in value.values():
            _collect_runs(item, runs)
    elif isinstance(value, list):
        for item in value:
            _collect_runs(item, runs)
