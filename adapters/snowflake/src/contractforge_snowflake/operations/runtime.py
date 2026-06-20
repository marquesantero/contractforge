"""Record ContractForge operations metadata in Snowflake evidence tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence import record_operations_evidence
from contractforge_snowflake.values import dict_mapping as _mapping
from contractforge_snowflake.values import pipe_string_list as _as_list


@dataclass(frozen=True)
class SnowflakeOperationsResult:
    status: str
    commands: tuple[str, ...] = ()


def record_snowflake_operations(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
) -> SnowflakeOperationsResult:
    if not _has_operations_metadata(contract):
        return SnowflakeOperationsResult(status="NOT_CONFIGURED")
    evidence = record_operations_evidence(
        session,
        environment=environment,
        contract=contract,
        run_id=run_id,
        payload=operations_payload(contract),
        status="RECORDED",
    )
    return SnowflakeOperationsResult(status="RECORDED", commands=evidence.commands)


def operations_payload(contract: SemanticContract) -> dict[str, Any]:
    raw = dict(contract.operations.metadata or {}) if contract.operations and contract.operations.metadata else {}
    ownership = _mapping(raw.get("ownership"))
    operations = _mapping(raw.get("operations")) or raw
    return {
        "criticality": operations.get("criticality"),
        "expected_frequency": operations.get("expected_frequency"),
        "freshness_sla_minutes": operations.get("freshness_sla_minutes"),
        "alert_on_failure": bool(operations.get("alert_on_failure", False)),
        "alert_on_quality_fail": bool(operations.get("alert_on_quality_fail", False)),
        "runbook_url": operations.get("runbook_url"),
        "ownership": ownership,
        "owners": _as_list(operations.get("owners")),
        "groups": _as_list(operations.get("groups")),
        "tags": _mapping(operations.get("tags")),
    }


def _has_operations_metadata(contract: SemanticContract) -> bool:
    return bool(contract.operations and contract.operations.metadata)


__all__ = ["SnowflakeOperationsResult", "operations_payload", "record_snowflake_operations"]
