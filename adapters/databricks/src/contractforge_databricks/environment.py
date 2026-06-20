"""Databricks interpretation of the core environment contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.contracts import validate_environment_contract
from contractforge_databricks.coercion import mapping


@dataclass(frozen=True)
class DatabricksEnvironment:
    name: str = "dev"
    evidence_catalog: str = "main"
    evidence_schema: str = "ops"
    workspace_path: str = "/Workspace/ContractForge"
    bundle_target: str = "dev"
    runtime_kind: str | None = None
    parameters: dict[str, Any] | None = None

    @classmethod
    def from_contract(cls, value: dict[str, Any] | None) -> "DatabricksEnvironment":
        if value is None:
            return cls()
        env = validate_environment_contract(value)
        if env["adapter"] != "databricks":
            raise ValueError("Databricks adapter requires environment.adapter='databricks'")
        runtime = mapping(env.get("runtime"))
        deployment = mapping(env.get("deployment"))
        evidence = mapping(env.get("evidence"))
        parameters = mapping(env.get("parameters")).get("databricks", {})
        return cls(
            name=str(env["name"]),
            evidence_catalog=str(evidence.get("catalog", "main")),
            evidence_schema=str(evidence.get("schema", "ops")),
            workspace_path=str(deployment.get("workspace_path", "/Workspace/ContractForge")).rstrip("/"),
            bundle_target=str(deployment.get("target", env["name"])),
            runtime_kind=_first_text(
                runtime.get("kind"),
                runtime.get("runtime_type"),
                parameters.get("runtime_kind"),
                parameters.get("runtime_type"),
                parameters.get("runtime"),
            ),
            parameters=dict(parameters) if isinstance(parameters, dict) else {},
        )

def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
