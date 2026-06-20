"""Execution helpers for the minimal AWS smoke test."""

from __future__ import annotations

import importlib
import time
from dataclasses import asdict
from typing import Any

from contractforge_aws.runtime import (
    publish_aws_contract_artifacts_to_s3,
    register_aws_glue_job,
    start_aws_glue_job_run,
    wait_aws_glue_job_run,
)
from contractforge_aws.smoke.environment import ensure_environment
from contractforge_aws.smoke.models import SmokeConfig, estimate_max_cost, smoke_contract

_WAIT_STARTUP_BUFFER_SECONDS = 300


def dry_run_payload(config: SmokeConfig, *, execute: bool) -> dict[str, Any]:
    return {
        "config": asdict(config),
        "role_arn": config.role_arn,
        "source_path": config.source_path,
        "warehouse_path": config.warehouse_path,
        "script_uri": config.script_uri,
        "contract": smoke_contract(config),
        "estimated_max_cost_usd": estimate_max_cost(config),
        "execute": execute,
    }


def execute_smoke(config: SmokeConfig, *, wait: bool) -> dict[str, Any]:
    runtime = _require_boto3().Session(region_name=config.region)
    ensure_environment(config, session=runtime)
    published = publish_aws_contract_artifacts_to_s3(
        smoke_contract(config),
        bucket=config.bucket,
        prefix=config.artifact_prefix,
        s3_client=runtime.client("s3"),
    )
    registration = register_aws_glue_job(
        job_name=config.job_name,
        role_arn=config.role_arn,
        script_s3_uri=config.script_uri,
        glue_client=runtime.client("glue"),
        worker_type=config.worker_type,
        number_of_workers=config.number_of_workers,
        timeout_minutes=config.timeout_minutes,
        max_retries=0,
        default_arguments={"--TempDir": f"s3://{config.bucket}/temp/"},
    )
    time.sleep(15)
    run = start_aws_glue_job_run(job_name=config.job_name, glue_client=runtime.client("glue"))
    payload = dry_run_payload(config, execute=True)
    payload.update(
        {
            "published": [asdict(item) for item in published],
            "registration": asdict(registration),
            "run": asdict(run),
        }
    )
    if wait:
        payload["status"] = asdict(_wait_for_run(config, run.run_id, glue_client=runtime.client("glue")))
    return payload


def _wait_for_run(config: SmokeConfig, run_id: str, *, glue_client: Any) -> Any:
    return wait_aws_glue_job_run(
        job_name=config.job_name,
        run_id=run_id,
        glue_client=glue_client,
        poll_interval_seconds=20.0,
        max_wait_seconds=(config.timeout_minutes * 60) + _WAIT_STARTUP_BUFFER_SECONDS,
    )


def _require_boto3() -> Any:
    try:
        return importlib.import_module("boto3")
    except ImportError as exc:
        raise RuntimeError("Install runtime dependencies with: pip install 'contractforge-aws[runtime]'") from exc
