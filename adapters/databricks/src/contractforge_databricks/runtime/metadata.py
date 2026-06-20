"""Runtime contract metadata payload helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract


def contract_metadata(contract: SemanticContract, operations: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": operations.get("description"),
        "owner": contract.governance.owner if contract.governance else None,
        "domain": contract.target.domain,
        "tags": operations.get("tags"),
        "sla": operations.get("sla"),
        "runtime_parameters": operations.get("runtime_parameters"),
        "operations": contract.operations.metadata if contract.operations else None,
        "applied_presets": operations.get("applied_presets"),
        "target_schema": contract.target.namespace,
    }
