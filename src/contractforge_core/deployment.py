"""Platform-neutral deployment ledger helpers."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, Mapping

DEPLOYMENT_LEDGER_TABLE = "ctrl_deployment_versions"
DEPLOYMENT_LEDGER_SCHEMA_VERSION = 1

DEPLOYMENT_LEDGER_COLUMNS = (
    "deployment_id",
    "deployment_step_id",
    "deployment_hash",
    "deployment_ts_utc",
    "deployment_date",
    "deployment_status",
    "adapter",
    "platform",
    "subtarget",
    "project_name",
    "project_path",
    "environment_key",
    "environment_path",
    "contract_name",
    "contract_path",
    "contract_layer",
    "target_table",
    "mode",
    "action",
    "artifact_kind",
    "artifact_name",
    "artifact_id",
    "artifact_uri",
    "definition_hash",
    "previous_definition_hash",
    "contract_hash",
    "environment_hash",
    "manifest_hash",
    "package_versions_json",
    "git_commit",
    "deployed_by",
    "deployment_config_json",
    "deployment_result_json",
    "created_at_utc",
    "framework_version",
    "ctrl_schema_version",
)


def new_deployment_id() -> str:
    """Return a unique deployment id for one adapter deploy command execution."""

    return f"dep_{uuid.uuid4().hex}"


def stable_hash(payload: Any) -> str:
    """Return a stable SHA-256 hash for JSON-serializable deployment content."""

    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def canonical_json(payload: Any) -> str:
    """Return deterministic JSON for hashing and ledger payload storage."""

    return json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deployment_step_id(*, deployment_id: str, contract_hash: str, step_name: str | None = None) -> str:
    """Return a deterministic id for one contract row inside a unique deployment."""

    return stable_hash(
        {
            "deployment_id": deployment_id,
            "contract_hash": contract_hash,
            "step_name": step_name or "",
        }
    )


def deployment_hash(record_payload: Mapping[str, Any]) -> str:
    """Return the row-level deployment hash excluding mutable result metadata."""

    ignored = {
        "deployment_hash",
        "deployment_result_json",
        "created_at_utc",
    }
    return stable_hash({key: value for key, value in record_payload.items() if key not in ignored})


def build_deployment_ledger_record(
    *,
    deployment_id: str,
    adapter: str,
    platform: str,
    deployment_ts_utc: datetime | None = None,
    step_name: str | None = None,
    project_name: str | None = None,
    project_path: str | None = None,
    environment_key: str | None = None,
    environment_path: str | None = None,
    contract_name: str | None = None,
    contract_path: str | None = None,
    contract_layer: str | None = None,
    target_table: str | None = None,
    mode: str | None = None,
    action: str | None = None,
    deployment_status: str | None = None,
    subtarget: str | None = None,
    artifact_kind: str | None = None,
    artifact_name: str | None = None,
    artifact_id: str | None = None,
    artifact_uri: str | None = None,
    definition_hash: str | None = None,
    previous_definition_hash: str | None = None,
    contract_payload: Mapping[str, Any] | None = None,
    environment_payload: Mapping[str, Any] | None = None,
    manifest_payload: Mapping[str, Any] | None = None,
    package_versions: Mapping[str, Any] | None = None,
    git_commit: str | None = None,
    deployed_by: str | None = None,
    deployment_config: Mapping[str, Any] | None = None,
    deployment_result: Mapping[str, Any] | None = None,
    framework_version: str | None = None,
) -> dict[str, Any]:
    """Build one platform-neutral deployment ledger row.

    A deployment command receives one unique ``deployment_id``. Each contract or
    project step creates one row with its own deterministic ``deployment_step_id``
    and content-derived ``deployment_hash``.
    """

    ts = _as_utc(deployment_ts_utc)
    contract_hash = stable_hash(contract_payload) if contract_payload is not None else None
    environment_hash = stable_hash(environment_payload) if environment_payload is not None else None
    manifest_hash = stable_hash(manifest_payload) if manifest_payload is not None else None
    step_id = deployment_step_id(
        deployment_id=deployment_id,
        contract_hash=contract_hash or stable_hash({"contract_path": contract_path, "contract_name": contract_name}),
        step_name=step_name or contract_name,
    )
    record: dict[str, Any] = {
        "deployment_id": deployment_id,
        "deployment_step_id": step_id,
        "deployment_hash": None,
        "deployment_ts_utc": ts,
        "deployment_date": ts.date(),
        "deployment_status": deployment_status,
        "adapter": adapter,
        "platform": platform,
        "subtarget": subtarget,
        "project_name": project_name,
        "project_path": project_path,
        "environment_key": environment_key,
        "environment_path": environment_path,
        "contract_name": contract_name or step_name,
        "contract_path": contract_path,
        "contract_layer": contract_layer,
        "target_table": target_table,
        "mode": mode,
        "action": action,
        "artifact_kind": artifact_kind,
        "artifact_name": artifact_name,
        "artifact_id": artifact_id,
        "artifact_uri": artifact_uri,
        "definition_hash": definition_hash,
        "previous_definition_hash": previous_definition_hash,
        "contract_hash": contract_hash,
        "environment_hash": environment_hash,
        "manifest_hash": manifest_hash,
        "package_versions_json": canonical_json(package_versions or {}),
        "git_commit": git_commit,
        "deployed_by": deployed_by,
        "deployment_config_json": canonical_json(deployment_config or {}),
        "deployment_result_json": canonical_json(deployment_result or {}),
        "created_at_utc": datetime.now(timezone.utc),
        "framework_version": framework_version,
        "ctrl_schema_version": DEPLOYMENT_LEDGER_SCHEMA_VERSION,
    }
    record["deployment_hash"] = deployment_hash(record)
    return {column: record.get(column) for column in DEPLOYMENT_LEDGER_COLUMNS}


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


__all__ = [
    "DEPLOYMENT_LEDGER_COLUMNS",
    "DEPLOYMENT_LEDGER_SCHEMA_VERSION",
    "DEPLOYMENT_LEDGER_TABLE",
    "build_deployment_ledger_record",
    "canonical_json",
    "deployment_hash",
    "deployment_step_id",
    "new_deployment_id",
    "stable_hash",
]
