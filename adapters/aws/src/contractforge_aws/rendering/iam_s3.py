"""S3 resource derivation for AWS IAM review artifacts."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from contractforge_core.semantic import SemanticContract
from contractforge_aws.contract_extensions import aws_extensions


def s3_policy_uris(
    contract: SemanticContract,
    *,
    environment_parameters: dict[str, Any] | None,
    artifact_uri: str | None,
) -> list["_S3Uri"]:
    source = contract.source.raw or {}
    prefix_values: list[object] = [source.get("path"), source.get("checkpoint_location"), artifact_uri]
    iceberg = aws_extensions(contract).get("iceberg")
    if isinstance(iceberg, dict):
        prefix_values.append(iceberg.get("warehouse"))
    exact_values = _runtime_s3_values(contract, environment_parameters)
    prefix_uris = [_parse_s3(value, exact=False) for value in prefix_values]
    exact_uris = [_parse_s3(value, exact=True) for value in exact_values]
    return [uri for uri in (*prefix_uris, *exact_uris) if uri is not None]


class _S3Uri:
    def __init__(self, bucket: str, prefix: str, *, exact: bool) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.exact = exact

    @property
    def object_arn(self) -> str:
        if self.exact and self.prefix:
            return f"{bucket_arn(self.bucket)}/{self.prefix}"
        suffix = f"{self.prefix}/*" if self.prefix else "*"
        return f"{bucket_arn(self.bucket)}/{suffix}"


def bucket_arn(bucket: str) -> str:
    return f"arn:aws:s3:::{bucket}"


def _runtime_s3_values(contract: SemanticContract, environment_parameters: dict[str, Any] | None) -> list[object]:
    dependencies = _merged_adapter_map("dependencies", contract, environment_parameters)
    glue_job = _merged_adapter_map("glue_job", contract, environment_parameters)
    values: list[object] = [glue_job.get("script_s3_uri")]
    for key in ("extra_py_files", "py_files", "extra_jars", "jars"):
        values.extend(_split_s3_list(dependencies.get(key)))
    return values


def _merged_adapter_map(
    name: str,
    contract: SemanticContract,
    environment_parameters: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = _mapping((environment_parameters or {}).get(name))
    merged.update(_mapping(aws_extensions(contract).get(name)))
    return merged


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _split_s3_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _parse_s3(value: object, *, exact: bool) -> _S3Uri | None:
    text = str(value or "").strip()
    if not text.startswith("s3://"):
        return None
    parsed = urlparse(text)
    if not parsed.netloc:
        return None
    return _S3Uri(parsed.netloc, parsed.path, exact=exact)

