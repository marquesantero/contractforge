"""Publish rendered ContractForge AWS artifacts to S3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from contractforge_core.adapters import RenderedArtifacts
from contractforge_aws.runtime.dependencies import require_boto3


@dataclass(frozen=True)
class PublishedArtifact:
    name: str
    bucket: str
    key: str
    uri: str
    bytes_written: int


def publish_rendered_artifacts_to_s3(
    artifacts: RenderedArtifacts,
    *,
    bucket: str,
    prefix: str = "",
    s3_client: Any | None = None,
) -> tuple[PublishedArtifact, ...]:
    """Upload rendered artifacts to S3.

    Passing ``s3_client`` is supported for tests and for callers that manage
    their own boto3 session. If omitted, boto3 is imported lazily from the
    optional ``contractforge-aws[runtime]`` dependency set.
    """

    if not bucket or not str(bucket).strip():
        raise ValueError("bucket is required")
    client = s3_client or require_boto3().client("s3")
    normalized_prefix = _normalize_prefix(prefix)
    published: list[PublishedArtifact] = []
    for name, body in sorted(artifacts.artifacts.items()):
        key = f"{normalized_prefix}{_artifact_key(name)}"
        payload_body = materialize_published_artifact_body(
            name,
            str(body),
            bucket=str(bucket),
            normalized_prefix=normalized_prefix,
            artifact_names=artifacts.artifacts.keys(),
        )
        payload = payload_body.encode("utf-8")
        client.put_object(
            Bucket=str(bucket),
            Key=key,
            Body=payload,
            ContentType=_content_type(name),
        )
        published.append(
            PublishedArtifact(
                name=name,
                bucket=str(bucket),
                key=key,
                uri=f"s3://{bucket}/{key}",
                bytes_written=len(payload),
            )
        )
    return tuple(published)


def parse_s3_artifact_uri(uri: str) -> tuple[str, str]:
    """Return ``(bucket, prefix)`` for an ``s3://`` artifact destination."""

    parsed = urlparse(str(uri).strip())
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError("artifact URI must be an s3:// URI")
    prefix = parsed.path.strip("/")
    return parsed.netloc, prefix


def materialize_published_artifact_body(
    name: str,
    body: str,
    *,
    bucket: str,
    normalized_prefix: str,
    artifact_names: Any,
) -> str:
    if not name.endswith(".glue_job_definition.json"):
        return body
    artifact_name_set = set(artifact_names)
    script_name = _script_artifact_name(name, artifact_name_set)
    if not script_name:
        return body
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body
    command = payload.get("Command")
    if not isinstance(command, dict):
        return body
    script_key = f"{normalized_prefix}{_artifact_key(script_name)}"
    command["ScriptLocation"] = f"s3://{bucket}/{script_key}"
    _materialize_contractforge_arguments(payload, bucket=bucket, normalized_prefix=normalized_prefix)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _script_artifact_name(name: str, artifact_names: set[str]) -> str | None:
    if "runtime/contractforge_aws_runner.py" in artifact_names:
        return "runtime/contractforge_aws_runner.py"
    generated = name[: -len(".glue_job_definition.json")] + ".glue_job.py"
    return generated if generated in artifact_names else None


def _materialize_contractforge_arguments(payload: dict[str, Any], *, bucket: str, normalized_prefix: str) -> None:
    arguments = payload.get("DefaultArguments")
    if not isinstance(arguments, dict):
        return
    for key, value in list(arguments.items()):
        if not isinstance(value, str) or "${artifact_bucket}" not in value:
            continue
        arguments[key] = (
            value.replace("${artifact_bucket}", str(bucket)).replace("${artifact_prefix}/", normalized_prefix)
        )


def _normalize_prefix(prefix: str) -> str:
    text = str(prefix or "").strip().strip("/")
    if not text:
        return ""
    return f"{text}/"


def _artifact_key(name: str) -> str:
    text = str(name).strip().replace("\\", "/").lstrip("/")
    if not text or ".." in text.split("/"):
        raise ValueError(f"invalid artifact name for S3 key: {name!r}")
    return text


def _content_type(name: str) -> str:
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".md"):
        return "text/markdown; charset=utf-8"
    if name.endswith(".py"):
        return "text/x-python; charset=utf-8"
    if name.endswith(".sql"):
        return "application/sql; charset=utf-8"
    if name.endswith((".yml", ".yaml")):
        return "application/yaml; charset=utf-8"
    return "text/plain; charset=utf-8"
