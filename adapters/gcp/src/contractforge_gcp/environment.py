"""Google Cloud adapter environment settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GCPEnvironment:
    project_id: str | None = None
    location: str | None = None
    dataset: str | None = None
    evidence_dataset: str | None = None
    staging_bucket: str | None = None
    service_account: str | None = None

    @classmethod
    def from_contract(cls, environment: dict[str, Any] | None = None) -> "GCPEnvironment":
        payload = environment or {}
        parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
        gcp = parameters.get("gcp") if isinstance(parameters.get("gcp"), dict) else {}
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        return cls(
            project_id=_string(gcp.get("project_id") or gcp.get("project") or payload.get("project_id")),
            location=_string(gcp.get("location") or gcp.get("region") or payload.get("location")),
            dataset=_string(gcp.get("dataset") or gcp.get("bigquery_dataset") or payload.get("dataset")),
            evidence_dataset=_string(evidence.get("dataset") or gcp.get("evidence_dataset")),
            staging_bucket=_string(gcp.get("staging_bucket") or artifacts.get("bucket")),
            service_account=_string(gcp.get("service_account") or payload.get("service_account")),
        )


def _string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
