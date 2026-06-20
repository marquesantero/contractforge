"""Runtime check/apply facade for Databricks governance contracts."""

from __future__ import annotations

from typing import Any

from contractforge_core.results import GovernanceApplyResult
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.annotations import annotation_steps, apply_annotations_contract
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.governance.access import access_steps
from contractforge_databricks.governance.application import apply_access_contract


def check_governance_contract(contract: SemanticContract) -> dict[str, Any]:
    """Return reviewable governance SQL without executing it."""

    annotation_sql = tuple(str(step["sql"]) for step in annotation_steps(contract))
    access_sql = tuple(str(step["sql"]) for step in access_steps(contract))
    total = len(annotation_sql) + len(access_sql)
    return {
        "status": "VALIDATED" if total else "NOT_CONFIGURED",
        "annotations": GovernanceApplyResult(status="VALIDATED" if annotation_sql else "NOT_CONFIGURED", validated=len(annotation_sql), sql_preview=annotation_sql),
        "access": GovernanceApplyResult(status="VALIDATED" if access_sql else "NOT_CONFIGURED", validated=len(access_sql), sql_preview=access_sql),
        "sql_preview": annotation_sql + access_sql,
        "validated": total,
    }


def apply_governance_contract(*, runner: SqlRunner, contract: SemanticContract) -> dict[str, Any]:
    """Apply annotations and access governance using an injected Databricks SQL runner."""

    annotations = apply_annotations_contract(runner=runner, contract=contract)
    access = apply_access_contract(runner=runner, contract=contract)
    return {
        "status": _combined_status(annotations, access),
        "annotations": annotations,
        "access": access,
        "applied": annotations.applied + access.applied,
        "validated": annotations.validated + access.validated,
        "ignored": annotations.ignored + access.ignored,
        "failed": annotations.failed + access.failed,
        "sql_preview": annotations.sql_preview + access.sql_preview,
        "errors": annotations.errors + access.errors,
    }


def _combined_status(*results: GovernanceApplyResult) -> str:
    statuses = {result.status for result in results}
    if "FAILED" in statuses:
        return "FAILED"
    if "WARNED" in statuses:
        return "WARNED"
    if "SUCCESS" in statuses:
        return "SUCCESS"
    if "VALIDATED" in statuses:
        return "VALIDATED"
    if "IGNORED" in statuses:
        return "IGNORED"
    return "NOT_CONFIGURED"
