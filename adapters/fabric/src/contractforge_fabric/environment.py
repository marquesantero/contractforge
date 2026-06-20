"""Fabric adapter environment binding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FabricEnvironment:
    """Adapter-owned interpretation of the core environment contract."""

    workspace_id: str | None = None
    workspace_name: str | None = None
    tenant_id: str | None = None
    tenant_domain: str | None = None
    lakehouse_id: str | None = None
    lakehouse_name: str | None = None
    warehouse_id: str | None = None
    warehouse_name: str | None = None
    evidence_lakehouse: str | None = None
    evidence_schema: str | None = None
    artifact_uri: str | None = None
    runtime_kind: str | None = None
    notebook_id: str | None = None
    notebook_name: str | None = None
    pipeline_id: str | None = None
    secret_vault_url: str | None = None
    secret_scopes: dict[str, str] | None = None

    @classmethod
    def from_contract(cls, environment: dict[str, Any] | None = None) -> "FabricEnvironment":
        if not environment:
            return cls()
        evidence = environment.get("evidence") if isinstance(environment.get("evidence"), dict) else {}
        artifacts = environment.get("artifacts") if isinstance(environment.get("artifacts"), dict) else {}
        secrets = environment.get("secrets") if isinstance(environment.get("secrets"), dict) else {}
        runtime = environment.get("runtime") if isinstance(environment.get("runtime"), dict) else {}
        parameters = environment.get("parameters") if isinstance(environment.get("parameters"), dict) else {}
        fabric = parameters.get("fabric") if isinstance(parameters.get("fabric"), dict) else {}
        secret_scopes = secrets.get("scopes") if isinstance(secrets.get("scopes"), dict) else {}
        return cls(
            workspace_id=fabric.get("workspace_id"),
            workspace_name=fabric.get("workspace_name"),
            tenant_id=fabric.get("tenant_id"),
            tenant_domain=fabric.get("tenant_domain"),
            lakehouse_id=fabric.get("lakehouse_id"),
            lakehouse_name=fabric.get("lakehouse_name"),
            warehouse_id=fabric.get("warehouse_id"),
            warehouse_name=fabric.get("warehouse_name"),
            evidence_lakehouse=evidence.get("lakehouse") or evidence.get("database"),
            evidence_schema=evidence.get("schema"),
            artifact_uri=artifacts.get("uri"),
            runtime_kind=runtime.get("kind"),
            notebook_id=fabric.get("notebook_id"),
            notebook_name=fabric.get("notebook_name"),
            pipeline_id=fabric.get("pipeline_id"),
            secret_vault_url=(
                secrets.get("vault_url")
                or secrets.get("key_vault_url")
                or secrets.get("azure_key_vault_url")
                or fabric.get("secret_vault_url")
                or fabric.get("key_vault_url")
            ),
            secret_scopes={str(key): str(value) for key, value in secret_scopes.items()},
        )
