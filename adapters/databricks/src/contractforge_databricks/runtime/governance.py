"""Runtime governance side effects for Databricks ingestion."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.annotations import apply_annotations_contract
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.execution import SqlRunner
from contractforge_databricks.operations import record_operations_contract


def apply_runtime_governance(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    run_id: str,
    evidence_catalog: str,
    evidence_schema: str,
) -> dict[str, Any]:
    operations = record_operations_contract(
        runner=runner,
        contract=contract,
        environment=DatabricksEnvironment(evidence_catalog=evidence_catalog, evidence_schema=evidence_schema),
        run_id=run_id,
    )
    annotations = apply_annotations_contract(runner=runner, contract=contract)
    result = {
        "operations": asdict(operations),
        "annotations": asdict(annotations),
        "access": {"status": "DEFERRED"} if contract.governance and contract.governance.access else {"status": "NOT_CONFIGURED"},
    }
    if annotations.status == "FAILED":
        raise ValueError(f"Databricks annotations failed: {list(annotations.errors)}")
    return result
