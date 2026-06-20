"""AWS interpretation of the core environment contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.contracts import validate_environment_contract


@dataclass(frozen=True)
class AWSEnvironment:
    name: str = "dev"
    evidence_database: str | None = None
    artifact_uri: str | None = None
    artifact_options: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None

    @classmethod
    def from_contract(cls, value: dict[str, Any] | None) -> "AWSEnvironment":
        if value is None:
            return cls()
        env = validate_environment_contract(value)
        if env["adapter"] != "aws":
            raise ValueError("AWS adapter requires environment.adapter='aws'")
        artifacts = _mapping(env.get("artifacts"))
        evidence = _mapping(env.get("evidence"))
        parameters = _mapping(env.get("parameters")).get("aws", {})
        database = evidence.get("database") or evidence.get("schema")
        artifact_uri = _artifact_uri(artifacts)
        return cls(
            name=str(env["name"]),
            evidence_database=str(database) if database else None,
            artifact_uri=artifact_uri,
            artifact_options=dict(artifacts) if artifacts else {},
            parameters=dict(parameters) if isinstance(parameters, dict) else {},
        )


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _artifact_uri(artifacts: dict[str, Any]) -> str | None:
    value = artifacts.get("uri") or artifacts.get("path")
    if value is None:
        return None
    uri = str(value).strip()
    if not uri:
        return None
    if not uri.startswith("s3://"):
        raise ValueError("AWS environment.artifacts.uri must be an s3:// URI")
    return uri
