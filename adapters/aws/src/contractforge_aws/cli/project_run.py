"""Run/wait helpers for AWS project-level deployment."""

from __future__ import annotations

import time
from dataclasses import asdict

from contractforge_aws.cli.project_cost import record_project_step_cost_evidence
from contractforge_aws.runtime import start_aws_glue_job_run, wait_aws_glue_job_run

_CONCURRENT_RUNS_EXCEEDED = "ConcurrentRunsExceededException"


def project_runtime_payload(
    *,
    enabled: bool,
    wait: bool,
    job_name: str,
    expected_failed: bool,
    accept_expected_failures: bool,
    record_cost_evidence: bool,
    environment: dict | None,
    contract: dict,
    athena_output_location: str | None,
    athena_workgroup: str | None,
    poll_interval_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    if not enabled:
        return {}
    run_result = start_project_step_run(
        job_name,
        poll_interval_seconds=poll_interval_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    payload: dict[str, object] = {"run": asdict(run_result)}
    if not wait:
        return payload
    payload["wait"] = wait_project_step(
        job_name,
        run_result.run_id,
        expected_failed=expected_failed,
        accept_expected_failures=accept_expected_failures,
        poll_interval_seconds=poll_interval_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    if record_cost_evidence:
        payload["cost_evidence"] = record_project_step_cost_evidence(
            environment,
            contract,
            job_name=job_name,
            run_id=run_result.run_id,
            athena_output_location=str(athena_output_location),
            athena_workgroup=athena_workgroup,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
        )
    return payload


def start_project_step_run(
    job_name: str,
    *,
    poll_interval_seconds: float,
    max_wait_seconds: float,
):
    deadline = time.monotonic() + max_wait_seconds
    while True:
        try:
            return start_aws_glue_job_run(job_name=job_name)
        except Exception as exc:
            if not _is_concurrent_runs_exceeded(exc):
                raise
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"AWS Glue job {job_name} could not start within {max_wait_seconds} seconds "
                    f"because concurrent runs were exceeded"
                ) from exc
            time.sleep(max(1.0, poll_interval_seconds))


def wait_project_step(
    job_name: str,
    run_id: str,
    *,
    expected_failed: bool,
    accept_expected_failures: bool,
    poll_interval_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    try:
        status = wait_aws_glue_job_run(
            job_name=job_name,
            run_id=run_id,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
        )
        return {"state": status.state, "status": "SUCCEEDED"}
    except RuntimeError as exc:
        if expected_failed and accept_expected_failures:
            return {"state": "FAILED", "status": "EXPECTED_FAILURE", "message": str(exc)}
        raise


def _is_concurrent_runs_exceeded(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    return error.get("Code") == _CONCURRENT_RUNS_EXCEEDED or exc.__class__.__name__ == _CONCURRENT_RUNS_EXCEEDED
