"""Extract contract metadata for AWS run evidence."""

from __future__ import annotations

from typing import Any

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract


def run_metadata_from_contract(contract: SemanticContract) -> dict[str, Any]:
    raw = dict(contract.operations.metadata or {}) if contract.operations and contract.operations.metadata else {}
    operations = _mapping(raw.get("operations")) or raw
    ownership = _mapping(raw.get("ownership"))
    table_annotations = _mapping((contract.governance.annotations or {}).get("table")) if contract.governance else {}
    owner = contract.governance.owner if contract.governance else None
    owner = owner or ownership.get("technical_owner") or ownership.get("business_owner") or ownership.get("steward")
    tags = _mapping(operations.get("tags")) or _mapping(table_annotations.get("tags"))
    payload = {
        "contract_description": table_annotations.get("description") or raw.get("description"),
        "contract_owner": owner,
        "contract_domain": contract.target.domain,
        "contract_tags_json": tags or None,
        "contract_sla": operations.get("sla") or operations.get("freshness_sla_minutes"),
        "runtime_parameters_json": operations.get("runtime_parameters") or raw.get("runtime_parameters"),
        "ownership_json": ownership or None,
        "operations_json": {"metadata": raw} if raw else None,
        "parent_run_id": raw.get("parent_run_id"),
        "run_group_id": raw.get("run_group_id"),
        "master_job_id": raw.get("master_job_id"),
        "master_run_id": raw.get("master_run_id"),
        "idempotency_key": raw.get("idempotency_key"),
        "idempotency_policy": raw.get("idempotency_policy"),
    }
    redacted = redact_value(payload)
    for field in ("parent_run_id", "run_group_id", "master_job_id", "master_run_id", "idempotency_key", "idempotency_policy"):
        redacted[field] = payload[field]
    return redacted


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
