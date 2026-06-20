"""Runtime-facing AWS adapter API.

These helpers may talk to AWS services when callers do not pass test clients.
They stay outside ``contractforge_aws.api`` so planning/rendering can remain a
small deterministic adapter boundary.
"""

from __future__ import annotations

from typing import Any

from contractforge_aws.api import render_aws_contract
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG
from contractforge_aws.environment import AWSEnvironment
from contractforge_aws.evidence import GlueJobRunEvidence, render_glue_run_evidence_sql
from contractforge_aws.runtime.glue_jobs import (
    GlueJobDefinition,
    GlueJobRegistration,
    GlueJobRun,
    GlueJobRunStatus,
    create_or_update_glue_job,
    create_or_update_glue_job_payload,
    get_glue_job_run_status,
    reconcile_glue_job_run_evidence,
    start_glue_job_run,
)
from contractforge_aws.runtime.glue_wait import wait_for_glue_job_run
from contractforge_aws.runtime.lakeformation_api import (
    apply_aws_lake_formation_contract,
    apply_aws_lake_formation_plan,
)
from contractforge_aws.runtime.publishable import publishable_artifacts
from contractforge_aws.runtime.s3_artifacts import PublishedArtifact, parse_s3_artifact_uri, publish_rendered_artifacts_to_s3


def publish_aws_contract_artifacts_to_s3(
    contract: dict[str, Any],
    *,
    bucket: str | None = None,
    prefix: str = "",
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    environment: dict[str, Any] | None = None,
    extra_artifacts: dict[str, str] | None = None,
    s3_client: Any | None = None,
) -> tuple[PublishedArtifact, ...]:
    bucket, prefix = _artifact_destination(bucket=bucket, prefix=prefix, environment=environment)
    artifacts = publishable_artifacts(
        contract,
        render_aws_contract(contract, subtarget=subtarget, environment=environment),
        environment=environment,
        extra_artifacts=extra_artifacts,
    )
    return publish_rendered_artifacts_to_s3(
        artifacts,
        bucket=bucket,
        prefix=prefix,
        s3_client=s3_client,
    )


def _artifact_destination(
    *,
    bucket: str | None,
    prefix: str,
    environment: dict[str, Any] | None,
) -> tuple[str, str]:
    if bucket:
        return bucket, prefix
    env = AWSEnvironment.from_contract(environment)
    if env.artifact_uri:
        return parse_s3_artifact_uri(env.artifact_uri)
    raise ValueError("AWS artifact publishing requires --bucket or environment.artifacts.uri")


def register_aws_glue_job(
    *,
    job_name: str,
    role_arn: str,
    script_s3_uri: str,
    glue_client: Any | None = None,
    glue_version: str = "4.0",
    worker_type: str = "G.1X",
    number_of_workers: int = 2,
    timeout_minutes: int = 60,
    max_retries: int = 0,
    enable_job_bookmark: bool = False,
    default_arguments: dict[str, str] | None = None,
) -> GlueJobRegistration:
    definition = GlueJobDefinition(
        name=job_name,
        role_arn=role_arn,
        script_s3_uri=script_s3_uri,
        glue_version=glue_version,
        worker_type=worker_type,
        number_of_workers=number_of_workers,
        timeout_minutes=timeout_minutes,
        max_retries=max_retries,
        enable_job_bookmark=enable_job_bookmark,
        default_arguments=default_arguments,
    )
    return create_or_update_glue_job(definition, glue_client=glue_client)


def register_aws_glue_job_definition_payload(
    payload: dict[str, Any] | str,
    *,
    glue_client: Any | None = None,
) -> GlueJobRegistration:
    return create_or_update_glue_job_payload(payload, glue_client=glue_client)


def start_aws_glue_job_run(
    *,
    job_name: str,
    arguments: dict[str, str] | None = None,
    glue_client: Any | None = None,
) -> GlueJobRun:
    return start_glue_job_run(job_name=job_name, arguments=arguments, glue_client=glue_client)


def get_aws_glue_job_run_status(
    *,
    job_name: str,
    run_id: str,
    glue_client: Any | None = None,
) -> GlueJobRunStatus:
    return get_glue_job_run_status(job_name=job_name, run_id=run_id, glue_client=glue_client)


def wait_aws_glue_job_run(
    *,
    job_name: str,
    run_id: str,
    glue_client: Any | None = None,
    poll_interval_seconds: float = 10.0,
    max_wait_seconds: float = 3600.0,
) -> GlueJobRunStatus:
    return wait_for_glue_job_run(
        job_name=job_name,
        run_id=run_id,
        glue_client=glue_client,
        poll_interval_seconds=poll_interval_seconds,
        max_wait_seconds=max_wait_seconds,
    )


def reconcile_aws_glue_job_run_evidence(
    *,
    job_name: str,
    run_id: str,
    target_table: str,
    mode: str,
    glue_client: Any | None = None,
) -> GlueJobRunEvidence:
    return reconcile_glue_job_run_evidence(
        job_name=job_name,
        run_id=run_id,
        target_table=target_table,
        mode=mode,
        glue_client=glue_client,
    )


def render_aws_glue_job_run_evidence_sql(
    *,
    job_name: str,
    run_id: str,
    target_table: str,
    mode: str,
    database: str = "contractforge_ops",
    glue_client: Any | None = None,
) -> str:
    evidence = reconcile_aws_glue_job_run_evidence(
        job_name=job_name,
        run_id=run_id,
        target_table=target_table,
        mode=mode,
        glue_client=glue_client,
    )
    return render_glue_run_evidence_sql(evidence, database=database)


__all__ = [
    "apply_aws_lake_formation_contract",
    "apply_aws_lake_formation_plan",
    "get_aws_glue_job_run_status",
    "publish_aws_contract_artifacts_to_s3",
    "reconcile_aws_glue_job_run_evidence",
    "register_aws_glue_job",
    "register_aws_glue_job_definition_payload",
    "render_aws_glue_job_run_evidence_sql",
    "start_aws_glue_job_run",
    "wait_aws_glue_job_run",
]
