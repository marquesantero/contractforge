"""Optional AWS Glue job registration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_aws.evidence import GlueJobRunEvidence, glue_job_run_evidence
from contractforge_aws.glue_job_definition import (
    CONTRACTFORGE_GLUE_ARGUMENTS,
    GlueJobDefinition,
    build_glue_job_payload,
    validate_glue_job_arguments,
)
from contractforge_aws.runtime.dependencies import require_boto3
from contractforge_aws.runtime.glue_job_payload import coerce_glue_job_payload
from contractforge_aws.validation import required_text


@dataclass(frozen=True)
class GlueJobRegistration:
    name: str
    action: str
    arn: str | None = None


@dataclass(frozen=True)
class GlueJobRun:
    job_name: str
    run_id: str


@dataclass(frozen=True)
class GlueJobRunStatus:
    job_name: str
    run_id: str
    state: str | None = None
    started_on: str | None = None
    completed_on: str | None = None
    error_message: str | None = None


def create_or_update_glue_job(
    definition: GlueJobDefinition,
    *,
    glue_client: Any | None = None,
) -> GlueJobRegistration:
    """Create or update an AWS Glue job definition.

    The helper registers the job definition only. It does not start a run.
    Passing ``glue_client`` keeps tests and custom sessions independent from
    boto3 import time. Without a client, boto3 is imported lazily.
    """

    payload = build_glue_job_payload(definition)
    client = glue_client or require_boto3().client("glue")
    if _job_exists(client, definition.name):
        response = client.update_job(JobName=definition.name, JobUpdate=payload)
        return GlueJobRegistration(name=definition.name, action="updated", arn=_job_arn(response))
    response = client.create_job(Name=definition.name, **payload)
    return GlueJobRegistration(name=definition.name, action="created", arn=_job_arn(response))


def create_or_update_glue_job_payload(
    payload: dict[str, Any] | str,
    *,
    glue_client: Any | None = None,
) -> GlueJobRegistration:
    """Create or update a Glue job from a rendered job-definition payload."""

    name, job_payload = coerce_glue_job_payload(payload)
    client = glue_client or require_boto3().client("glue")
    if _job_exists(client, name):
        response = client.update_job(JobName=name, JobUpdate=job_payload)
        return GlueJobRegistration(name=name, action="updated", arn=_job_arn(response))
    response = client.create_job(Name=name, **job_payload)
    return GlueJobRegistration(name=name, action="created", arn=_job_arn(response))


def start_glue_job_run(
    *,
    job_name: str,
    arguments: dict[str, str] | None = None,
    glue_client: Any | None = None,
) -> GlueJobRun:
    """Start a registered AWS Glue job.

    This is intentionally a thin runtime helper. It does not wait for
    completion and does not write ContractForge evidence.
    """

    name = required_text(job_name, "Glue job name")
    args = validate_glue_job_arguments(arguments or {}, reserved_keys=CONTRACTFORGE_GLUE_ARGUMENTS)
    client = glue_client or require_boto3().client("glue")
    payload: dict[str, Any] = {"JobName": name}
    if args:
        payload["Arguments"] = args
    response = client.start_job_run(**payload)
    run_id = response.get("JobRunId") if isinstance(response, dict) else None
    if not run_id:
        raise RuntimeError("AWS Glue start_job_run response did not include JobRunId")
    return GlueJobRun(job_name=name, run_id=str(run_id))


def get_glue_job_run_status(
    *,
    job_name: str,
    run_id: str,
    glue_client: Any | None = None,
) -> GlueJobRunStatus:
    name = required_text(job_name, "Glue job name")
    job_run_id = required_text(run_id, "Glue job run_id")
    client = glue_client or require_boto3().client("glue")
    response = client.get_job_run(JobName=name, RunId=job_run_id)
    job_run = response.get("JobRun", {}) if isinstance(response, dict) else {}
    return GlueJobRunStatus(
        job_name=name,
        run_id=job_run_id,
        state=_optional_text(job_run.get("JobRunState")),
        started_on=_optional_text(job_run.get("StartedOn")),
        completed_on=_optional_text(job_run.get("CompletedOn")),
        error_message=_optional_text(job_run.get("ErrorMessage") or job_run.get("StateDetail")),
    )


def reconcile_glue_job_run_evidence(
    *,
    job_name: str,
    run_id: str,
    target_table: str,
    mode: str,
    glue_client: Any | None = None,
) -> GlueJobRunEvidence:
    name = required_text(job_name, "Glue job name")
    job_run_id = required_text(run_id, "Glue job run_id")
    client = glue_client or require_boto3().client("glue")
    response = client.get_job_run(JobName=name, RunId=job_run_id)
    job_run = response.get("JobRun", {}) if isinstance(response, dict) else {}
    job_run.setdefault("Id", job_run_id)
    job_run.setdefault("JobName", name)
    return glue_job_run_evidence(job_run, target_table=target_table, mode=mode)


def _job_exists(client: Any, name: str) -> bool:
    try:
        client.get_job(JobName=name)
        return True
    except Exception as exc:  # boto3 exceptions are client-specific and created at runtime.
        if _is_entity_not_found(exc):
            return False
        raise


def _is_entity_not_found(exc: Exception) -> bool:
    code = getattr(exc, "response", {}).get("Error", {}).get("Code") if hasattr(exc, "response") else None
    return code in {"EntityNotFoundException", "EntityNotFound"}


def _job_arn(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    return response.get("Name") or response.get("JobName")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
