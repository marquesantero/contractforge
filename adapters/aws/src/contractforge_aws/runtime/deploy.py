"""End-to-end AWS deployment pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_aws.api import render_aws_contract
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG
from contractforge_aws.runtime.glue_jobs import create_or_update_glue_job_payload
from contractforge_aws.runtime.s3_artifacts import (
    PublishedArtifact,
    materialize_published_artifact_body,
    publish_rendered_artifacts_to_s3,
)
from contractforge_aws.runtime.api import _artifact_destination
from contractforge_aws.runtime.publishable import publishable_artifacts


@dataclass(frozen=True)
class AWSGlueContractDeployment:
    job_name: str
    action: str
    job_arn: str | None
    job_definition_uri: str
    script_uri: str
    artifacts: tuple[PublishedArtifact, ...]


def deploy_aws_contract_to_glue(
    contract: dict[str, Any],
    *,
    bucket: str | None = None,
    prefix: str = "",
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    environment: dict[str, Any] | None = None,
    extra_artifacts: dict[str, str] | None = None,
    s3_client: Any | None = None,
    glue_client: Any | None = None,
) -> AWSGlueContractDeployment:
    """Render, publish and register one contract as an AWS Glue job."""

    bucket, prefix = _artifact_destination(bucket=bucket, prefix=prefix, environment=environment)
    rendered = render_aws_contract(contract, subtarget=subtarget, environment=environment)
    publishable = publishable_artifacts(
        contract,
        rendered,
        environment=environment,
        extra_artifacts=extra_artifacts,
    )
    published = publish_rendered_artifacts_to_s3(
        publishable,
        bucket=bucket,
        prefix=prefix,
        s3_client=s3_client,
    )
    definition_name, definition_body = _job_definition_artifact(publishable)
    materialized = materialize_published_artifact_body(
        definition_name,
        definition_body,
        bucket=bucket,
        normalized_prefix=_normalized_prefix(prefix),
        artifact_names=publishable.artifacts.keys(),
    )
    registration = create_or_update_glue_job_payload(materialized, glue_client=glue_client)
    payload = json.loads(materialized)
    return AWSGlueContractDeployment(
        job_name=registration.name,
        action=registration.action,
        job_arn=registration.arn,
        job_definition_uri=_published_uri(published, definition_name),
        script_uri=str(payload["Command"]["ScriptLocation"]),
        artifacts=published,
    )


def _job_definition_artifact(artifacts: RenderedArtifacts) -> tuple[str, str]:
    for name, body in sorted(artifacts.artifacts.items()):
        if name.endswith(".glue_job_definition.json"):
            return name, str(body)
    raise ValueError("AWS Glue deployment requires a rendered .glue_job_definition.json artifact")


def _published_uri(published: tuple[PublishedArtifact, ...], name: str) -> str:
    for artifact in published:
        if artifact.name == name:
            return artifact.uri
    raise RuntimeError(f"published artifact not found: {name}")


def _normalized_prefix(prefix: str) -> str:
    text = str(prefix or "").strip().strip("/")
    return f"{text}/" if text else ""
