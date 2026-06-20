"""AWS project step deployment helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contractforge_aws.cli.project_run import project_runtime_payload
from contractforge_aws.cli.project_support import deployment_payload
from contractforge_aws.cli.support import contract_bundle_artifacts
from contractforge_aws.runtime import deploy_aws_contract_to_glue


def deploy_project_step(
    step: dict,
    *,
    contract_path: Path,
    contract: dict,
    environment: dict | None,
    bucket: str | None,
    prefix: str,
    run: bool,
    wait: bool,
    poll_interval_seconds: float,
    max_wait_seconds: float,
    accept_expected_failures: bool,
    record_cost_evidence: bool,
    athena_output_location: str | None,
    athena_workgroup: str | None,
    summary_only: bool,
    deployer=deploy_aws_contract_to_glue,
) -> dict[str, object]:
    deployment = deployer(
        contract,
        bucket=bucket,
        prefix=prefix,
        environment=environment,
        extra_artifacts=contract_bundle_artifacts(contract_path, environment=environment),
    )
    payload: dict[str, object] = {
        "name": str(step.get("name") or contract_path.stem),
        "contract": str(contract_path),
        "expected_result": str(step.get("expected_result") or "succeeded"),
        "deployment": deployment_payload(deployment, summary_only=summary_only),
    }
    payload.update(
        project_runtime_payload(
            enabled=run,
            wait=wait,
            job_name=deployment.job_name,
            expected_failed=payload["expected_result"] == "failed",
            accept_expected_failures=accept_expected_failures,
            record_cost_evidence=record_cost_evidence,
            environment=environment,
            contract=contract,
            athena_output_location=athena_output_location,
            athena_workgroup=athena_workgroup,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
        )
    )
    return payload
