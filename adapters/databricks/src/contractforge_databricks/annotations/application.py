"""Apply Databricks annotations with an injected SQL runner."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_core.results import GovernanceApplyResult
from contractforge_databricks.annotations.sql import annotation_steps
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.security import exception_message


def apply_annotations_contract(*, runner: SqlRunner, contract: SemanticContract) -> GovernanceApplyResult:
    steps = annotation_steps(contract)
    if not steps:
        return GovernanceApplyResult(status="NOT_CONFIGURED")
    policy = _policy(contract)
    sql_preview = tuple(str(step["sql"]) for step in steps)
    if policy == "ignore":
        return GovernanceApplyResult(status="IGNORED", ignored=len(steps), sql_preview=sql_preview)

    applied = 0
    errors: list[str] = []
    for statement in sql_preview:
        try:
            runner.sql(statement)
            applied += 1
        except Exception as exc:
            errors.append(exception_message(exc))
            if policy == "fail":
                return GovernanceApplyResult(
                    status="FAILED",
                    applied=applied,
                    failed=len(errors),
                    sql_preview=sql_preview,
                    errors=tuple(errors),
                )
    if errors:
        return GovernanceApplyResult(
            status="WARNED",
            applied=applied,
            failed=len(errors),
            sql_preview=sql_preview,
            errors=tuple(errors),
        )
    return GovernanceApplyResult(status="SUCCESS", applied=applied, sql_preview=sql_preview)


def _policy(contract: SemanticContract) -> str:
    annotations = contract.governance.annotations if contract.governance else None
    if isinstance(annotations, dict):
        return str(annotations.get("policy", "warn"))
    return "warn"
