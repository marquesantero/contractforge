"""Apply Databricks access governance with an injected SQL runner."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_core.results import GovernanceApplyResult
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.governance.access import access_steps, revoke_grant_steps
from contractforge_databricks.governance.drift import current_contract_grants
from contractforge_databricks.governance.validation import access_drift_report
from contractforge_databricks.security import exception_message


def apply_access_contract(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    allow_revoke_unmanaged: bool = False,
) -> GovernanceApplyResult:
    steps = access_steps(contract)
    if not steps:
        return GovernanceApplyResult(status="NOT_CONFIGURED")
    drift = _drift(runner, contract)
    if drift and drift["status"] == "DRIFTED" and _access_setting(contract, "on_drift", "warn") == "fail":
        return GovernanceApplyResult(
            status="FAILED",
            failed=len(drift["issues"]) or 1,
            sql_preview=tuple(str(step["sql"]) for step in steps),
            errors=tuple(str(issue["message"]) for issue in drift["issues"]),
        )
    if _revoke_unmanaged(contract) and drift and drift["unmanaged_grants"]:
        if not allow_revoke_unmanaged:
            return GovernanceApplyResult(
                status="FAILED",
                failed=len(drift["unmanaged_grants"]),
                sql_preview=tuple(str(step["sql"]) for step in steps),
                errors=("access.revoke_unmanaged requires explicit allow_revoke_unmanaged=True",),
            )
        steps = [*steps, *revoke_grant_steps(contract, drift["unmanaged_grants"])]
    sql_preview = tuple(str(step["sql"]) for step in steps)
    mode = _access_setting(contract, "mode", "apply")
    if mode == "ignore":
        return GovernanceApplyResult(status="IGNORED", ignored=len(steps), sql_preview=sql_preview)
    if mode == "validate_only":
        return GovernanceApplyResult(status="VALIDATED", validated=len(steps), sql_preview=sql_preview)

    applied = 0
    errors: list[str] = []
    fail_fast = _access_setting(contract, "on_drift", "warn") == "fail"
    for statement in sql_preview:
        try:
            runner.sql(statement)
            applied += 1
        except Exception as exc:
            errors.append(exception_message(exc))
            if fail_fast:
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


def _access_setting(contract: SemanticContract, key: str, default: str) -> str:
    access = contract.governance.access if contract.governance else None
    if not isinstance(access, dict):
        return default
    policy = access.get("access_policy", {})
    if isinstance(policy, dict) and policy.get(key) is not None:
        return str(policy[key])
    return str(access.get(key, default))


def _revoke_unmanaged(contract: SemanticContract) -> bool:
    return _access_setting(contract, "revoke_unmanaged", "false").lower() == "true"


def _drift(runner: SqlRunner, contract: SemanticContract) -> dict[str, object] | None:
    current = current_contract_grants(runner, contract)
    if current is None:
        return None
    return access_drift_report(contract, current_grants=current)
