"""Public AWS deployment-rendering helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG
from contractforge_aws.environment import AWSEnvironment
from contractforge_aws.rendering import (
    render_glue_job_cloudformation,
    render_glue_job_definition,
    render_glue_job_iam_policy,
    render_glue_job_terraform,
)
from contractforge_aws.subtargets import validate_aws_subtarget


def render_aws_glue_job_iam_policy(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    environment: dict[str, Any] | None = None,
) -> str:
    """Render a review IAM policy for the generated AWS Glue job role."""

    validate_aws_subtarget(subtarget)
    env = AWSEnvironment.from_contract(environment)
    return render_glue_job_iam_policy(
        semantic_contract_from_mapping(contract),
        evidence_database_name=env.evidence_database,
        environment_parameters=env.parameters,
        artifact_uri=env.artifact_uri,
    )


def render_aws_glue_job_definition(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    environment: dict[str, Any] | None = None,
) -> str:
    """Render a deterministic AWS Glue create/update job payload."""

    validate_aws_subtarget(subtarget)
    env = AWSEnvironment.from_contract(environment)
    return render_glue_job_definition(
        semantic_contract_from_mapping(contract),
        environment_parameters=env.parameters,
    )


def render_aws_glue_job_cloudformation(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    environment: dict[str, Any] | None = None,
) -> str:
    """Render a parameterized CloudFormation scaffold for the Glue job."""

    validate_aws_subtarget(subtarget)
    env = AWSEnvironment.from_contract(environment)
    return render_glue_job_cloudformation(
        semantic_contract_from_mapping(contract),
        evidence_database_name=env.evidence_database,
        environment_parameters=env.parameters,
    )


def render_aws_glue_job_terraform(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    environment: dict[str, Any] | None = None,
) -> str:
    """Render a Terraform scaffold for the Glue job."""

    validate_aws_subtarget(subtarget)
    env = AWSEnvironment.from_contract(environment)
    return render_glue_job_terraform(
        semantic_contract_from_mapping(contract),
        evidence_database_name=env.evidence_database,
        environment_parameters=env.parameters,
    )
