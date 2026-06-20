"""Secret Manager review planning for GCP source credentials."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from contractforge_core.connectors import is_http_file_source, is_rest_api_connector
from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment

SECRET_PLACEHOLDER_RE = re.compile(r"\{\{\s*secret:([^}]+)\}\}", re.IGNORECASE)


@dataclass(frozen=True)
class SecretRef:
    field_path: str
    scope: str
    key: str

    @property
    def contract_ref(self) -> str:
        return f"{self.scope}/{self.key}"

    @property
    def suggested_secret_id(self) -> str:
        value = re.sub(r"[^A-Za-z0-9_-]+", "-", self.contract_ref).strip("-")
        return value or "contractforge-secret"


def render_gcp_source_secret_resolution_plan(contract: SemanticContract, env: GCPEnvironment) -> str:
    """Render a deterministic Secret Manager review plan for authenticated sources."""

    source = contract.source.raw or {}
    if not _is_http_or_rest_source(source) or not _has_auth(source):
        return ""

    refs = secret_placeholder_refs(source)
    project = env.project_id or "PROJECT_ID"
    service_account = env.service_account or "SERVICE_ACCOUNT_EMAIL"
    blockers: list[dict[str, str]] = []
    if not refs:
        blockers.append(
            {
                "code": "NO_SECRET_PLACEHOLDER",
                "message": (
                    "Authenticated GCP REST/HTTP sources must use {{ secret:scope/key }} placeholders before "
                    "rendering an executable runtime path."
                ),
            }
        )
    if not env.project_id:
        blockers.append(
            {"code": "MISSING_PROJECT_ID", "message": "Set parameters.gcp.project_id for Secret Manager resource names."}
        )
    source_type = str(source.get("connector") or source.get("type") or "").strip().lower()
    secret_entries = [_secret_entry(ref, project=project, service_account=service_account) for ref in refs]
    payload: dict[str, Any] = {
        "kind": "contractforge.gcp.source_secret_resolution_plan.v1",
        "status": "PLANNED",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "source_type": source_type,
        "execution": {
            "included": bool(refs) and bool(env.project_id),
            "reason": (
                "Secret Manager values are resolved at runtime immediately before the shared core REST/HTTP reader runs."
            ),
        },
        "auth_redacted": redact_value(source.get("auth")),
        "secret_manager": {
            "project_id": project,
            "runtime_service_account": service_account,
            "required_role": "roles/secretmanager.secretAccessor",
        },
        "secret_refs": secret_entries,
        "blockers": blockers,
        "promotion_evidence_required": [
            "Secret versions exist in Secret Manager and are not embedded in generated artifacts.",
            "The runtime service account has roles/secretmanager.secretAccessor only for declared secrets.",
            "The authenticated endpoint passes a real GCP smoke through the shared core reader and BigQuery load path.",
            "Run, source metadata, quality, lineage and error evidence are recorded for success and failure paths.",
        ],
        "review_boundaries": [
            "This artifact does not read or print secret values.",
            "Inline credentials are not acceptable for promotion; use {{ secret:scope/key }} placeholders.",
            "Runtime execution requires the invoking identity to have roles/secretmanager.secretAccessor on declared secrets.",
        ],
        "sources": [
            "https://docs.cloud.google.com/secret-manager/docs/access-control",
            "https://docs.cloud.google.com/secret-manager/docs/access-secret-version",
            "https://docs.cloud.google.com/sdk/gcloud/reference/secrets/versions/access",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def secret_placeholder_refs(value: Any) -> tuple[SecretRef, ...]:
    refs: list[SecretRef] = []
    _collect_refs(value, path="$", refs=refs)
    deduped: dict[tuple[str, str, str], SecretRef] = {}
    for ref in refs:
        deduped[(ref.field_path, ref.scope, ref.key)] = ref
    return tuple(deduped.values())


def has_secret_placeholders(value: Any) -> bool:
    return bool(secret_placeholder_refs(value))


def _collect_refs(value: Any, *, path: str, refs: list[SecretRef]) -> None:
    if isinstance(value, str):
        for match in SECRET_PLACEHOLDER_RE.finditer(value):
            scope, key = _parse_ref(match.group(1))
            refs.append(SecretRef(field_path=path, scope=scope, key=key))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _collect_refs(item, path=f"{path}.{key}", refs=refs)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _collect_refs(item, path=f"{path}[{index}]", refs=refs)


def _parse_ref(value: str) -> tuple[str, str]:
    ref = value.strip()
    if "/" not in ref:
        return ref, ""
    scope, key = ref.split("/", 1)
    return scope.strip(), key.strip()


def _secret_entry(ref: SecretRef, *, project: str, service_account: str) -> dict[str, Any]:
    version_resource = f"projects/{project}/secrets/{ref.suggested_secret_id}/versions/latest"
    return {
        "field_path": ref.field_path,
        "contract_ref": ref.contract_ref,
        "scope": ref.scope,
        "key": ref.key,
        "suggested_secret_id": ref.suggested_secret_id,
        "version_resource": version_resource,
        "access_command": [
            "gcloud",
            "secrets",
            "versions",
            "access",
            "latest",
            f"--secret={ref.suggested_secret_id}",
            f"--project={project}",
        ],
        "iam_command": [
            "gcloud",
            "secrets",
            "add-iam-policy-binding",
            ref.suggested_secret_id,
            f"--member=serviceAccount:{service_account}",
            "--role=roles/secretmanager.secretAccessor",
            f"--project={project}",
        ],
    }


def _is_http_or_rest_source(source: dict[str, Any]) -> bool:
    return is_rest_api_connector(source) or is_http_file_source(source)


def _has_auth(source: dict[str, Any]) -> bool:
    auth = source.get("auth")
    if not isinstance(auth, dict):
        return False
    auth_type = str(auth.get("type") or "").strip().lower()
    return auth_type not in {"", "none"}
