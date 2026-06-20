"""Optional AWS Glue job run wait helpers."""

from __future__ import annotations

import time
from typing import Any

from contractforge_aws.runtime.glue_jobs import GlueJobRunStatus, get_glue_job_run_status

_TERMINAL_STATES = {"SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT", "ERROR"}
_MIN_POLL_INTERVAL_SECONDS = 1.0


def wait_for_glue_job_run(
    *,
    job_name: str,
    run_id: str,
    glue_client: Any | None = None,
    poll_interval_seconds: float = 10.0,
    max_wait_seconds: float = 3600.0,
) -> GlueJobRunStatus:
    deadline = time.monotonic() + max_wait_seconds
    while True:
        status = get_glue_job_run_status(job_name=job_name, run_id=run_id, glue_client=glue_client)
        if status.state in _TERMINAL_STATES:
            if status.state != "SUCCEEDED":
                raise RuntimeError(
                    f"AWS Glue job {job_name} run {run_id} ended with {status.state}: "
                    f"{status.error_message or 'no reason provided'}"
                )
            return status
        if time.monotonic() >= deadline:
            raise TimeoutError(f"AWS Glue job {job_name} run {run_id} did not finish within {max_wait_seconds} seconds")
        time.sleep(max(_MIN_POLL_INTERVAL_SECONDS, poll_interval_seconds))
