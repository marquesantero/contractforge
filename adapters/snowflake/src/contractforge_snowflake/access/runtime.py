"""Apply ContractForge access grants to Snowflake objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.security.redaction import redact_text
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence import record_access_evidence
from contractforge_snowflake.naming import quote_identifier, quote_multipart_identifier, snowflake_target_name
from contractforge_snowflake.session_ops import execute
from contractforge_snowflake.values import dict_mapping as _mapping
from contractforge_snowflake.values import string_list as _as_list


@dataclass(frozen=True)
class SnowflakeAccessStep:
    action: str
    access_type: str
    principal: str | None
    privilege: str | None
    column_name: str | None
    function_name: str | None
    object_name: str
    mode: str
    sql: str | None
    drift_policy: str = "warn"
    revoke_unmanaged: bool = False
    previous_value: str | None = None
    new_value: str | None = None


@dataclass(frozen=True)
class SnowflakeAccessResult:
    status: str
    applied: int
    skipped: int
    failed: int
    commands: tuple[str, ...]


def apply_snowflake_access(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
) -> SnowflakeAccessResult:
    steps = access_steps(contract)
    if not steps:
        return SnowflakeAccessResult(status="NOOP", applied=0, skipped=0, failed=0, commands=())
    commands: list[str] = []
    applied = skipped = failed = 0
    for step in steps:
        if step.mode != "apply":
            skipped += 1
            evidence = record_access_evidence(
                session,
                environment=environment,
                contract=contract,
                run_id=run_id,
                step=step.__dict__,
                status=_skipped_status(step.mode),
                error_message=None,
            )
            commands.extend(evidence.commands)
            continue
        try:
            if step.sql:
                execute(session, step.sql)
        except Exception as exc:
            failed += 1
            evidence = record_access_evidence(
                session,
                environment=environment,
                contract=contract,
                run_id=run_id,
                step=step.__dict__,
                status="FAILED",
                error_message=redact_text(str(exc)),
            )
            commands.extend(_with_sql(step.sql, evidence.commands))
            raise
        else:
            applied += 1
            evidence = record_access_evidence(
                session,
                environment=environment,
                contract=contract,
                run_id=run_id,
                step=step.__dict__,
                status="APPLIED",
                error_message=None,
            )
            commands.extend(_with_sql(step.sql, evidence.commands))
    return SnowflakeAccessResult(status="SUCCESS" if failed == 0 else "FAILED", applied=applied, skipped=skipped, failed=failed, commands=tuple(commands))


def access_steps(contract: SemanticContract) -> tuple[SnowflakeAccessStep, ...]:
    access = contract.governance.access if contract.governance else None
    if not isinstance(access, dict):
        return ()
    target = snowflake_target_name(contract)
    grants = _grant_steps(target, access)
    policies = _policy_steps(target, access)
    return (*grants, *policies)


def _grant_steps(target: str, access: dict[str, Any]) -> tuple[SnowflakeAccessStep, ...]:
    return tuple(
        _grant_step(target, principal=str(grant["principal"]), privilege=str(privilege), access=access)
        for grant in access.get("grants", ())
        if isinstance(grant, dict)
        for privilege in _as_list(grant.get("privileges"))
    )


def _grant_step(target: str, *, principal: str, privilege: str, access: dict[str, Any]) -> SnowflakeAccessStep:
    privilege_name = _privilege_name(privilege)
    return SnowflakeAccessStep(
        action="grant",
        access_type="grant",
        principal=principal,
        privilege=privilege_name,
        column_name=None,
        function_name=None,
        object_name=target,
        mode=_access_mode(access),
        sql=f"GRANT {privilege_name} ON TABLE {target} TO ROLE {quote_identifier(principal)}",
        drift_policy=_access_drift_policy(access),
        revoke_unmanaged=_revoke_unmanaged(access),
        new_value="GRANTED",
    )


def _policy_steps(target: str, access: dict[str, Any]) -> tuple[SnowflakeAccessStep, ...]:
    row_filters = tuple(
        _row_access_policy_step(target, item, access)
        for item in _iter_list_items(access.get("row_filters"))
    )
    masks = tuple(
        _masking_policy_step(target, item, access)
        for item in _iter_column_masks(access.get("column_masks"))
    )
    return (*row_filters, *masks)


def _row_access_policy_step(target: str, row_filter: dict[str, Any], access: dict[str, Any]) -> SnowflakeAccessStep:
    columns = tuple(_as_list(row_filter.get("columns")))
    policy = str(row_filter.get("function") or "").strip()
    if not columns:
        raise ValueError("Snowflake row access policy requires access.row_filters.columns")
    if not policy:
        raise ValueError("Snowflake row access policy requires access.row_filters.function")
    return SnowflakeAccessStep(
        action="apply_row_access_policy",
        access_type="row_filter",
        principal="|".join(_as_list(_mapping(row_filter.get("applies_to")).get("principals"))),
        privilege="ROW_ACCESS_POLICY",
        column_name="|".join(columns),
        function_name=policy,
        object_name=target,
        mode=_access_mode(access),
        sql=(
            f"ALTER TABLE {target} ADD ROW ACCESS POLICY {quote_multipart_identifier(policy)} "
            f"ON ({', '.join(quote_identifier(column) for column in columns)})"
        ),
        drift_policy=_access_drift_policy(access),
        revoke_unmanaged=_revoke_unmanaged(access),
        new_value=policy,
    )


def _masking_policy_step(target: str, column_mask: dict[str, Any], access: dict[str, Any]) -> SnowflakeAccessStep:
    column = str(column_mask.get("column") or "").strip()
    policy = str(column_mask.get("function") or "").strip()
    using_columns = tuple(_as_list(column_mask.get("using_columns")))
    if not column:
        raise ValueError("Snowflake masking policy requires access.column_masks.column")
    if not policy:
        raise ValueError("Snowflake masking policy requires access.column_masks.function")
    using_sql = ""
    if using_columns:
        using = (column, *tuple(item for item in using_columns if item != column))
        using_sql = " USING (" + ", ".join(quote_identifier(item) for item in using) + ")"
    return SnowflakeAccessStep(
        action="apply_masking_policy",
        access_type="column_mask",
        principal="|".join(_as_list(_mapping(column_mask.get("applies_to")).get("principals"))),
        privilege="MASKING_POLICY",
        column_name=column,
        function_name=policy,
        object_name=target,
        mode=_access_mode(access),
        sql=(
            f"ALTER TABLE {target} MODIFY COLUMN {quote_identifier(column)} "
            f"SET MASKING POLICY {quote_multipart_identifier(policy)}{using_sql}"
        ),
        drift_policy=_access_drift_policy(access),
        revoke_unmanaged=_revoke_unmanaged(access),
        new_value=policy,
    )


def _access_mode(access: dict[str, Any]) -> str:
    policy = _mapping(access.get("access_policy"))
    return str(policy.get("mode") or access.get("mode") or "apply")


def _access_drift_policy(access: dict[str, Any]) -> str:
    policy = _mapping(access.get("access_policy"))
    return str(policy.get("on_drift") or access.get("on_drift") or "warn")


def _revoke_unmanaged(access: dict[str, Any]) -> bool:
    policy = _mapping(access.get("access_policy"))
    return bool(policy.get("revoke_unmanaged", access.get("revoke_unmanaged", False)))


def _privilege_name(value: str) -> str:
    privilege = str(value).strip().replace("_", " ").upper()
    allowed = {
        "ALL PRIVILEGES",
        "APPLYBUDGET",
        "DELETE",
        "EVOLVE SCHEMA",
        "INSERT",
        "REFERENCES",
        "SELECT",
        "TRUNCATE",
        "UPDATE",
    }
    if privilege not in allowed:
        raise ValueError(f"Unsupported Snowflake table privilege: {value!r}")
    return privilege


def _skipped_status(mode: str) -> str:
    return "IGNORED" if mode == "ignore" else "VALIDATED"


def _iter_list_items(value: object) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, dict):
        return tuple(dict(item) for item in value.values() if isinstance(item, dict))
    return tuple(dict(item) for item in value if isinstance(item, dict))  # type: ignore[union-attr]


def _iter_column_masks(value: object) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, dict):
        return tuple({**dict(config), "column": column} for column, config in value.items() if isinstance(config, dict))
    return tuple(dict(item) for item in value if isinstance(item, dict))  # type: ignore[union-attr]


def _with_sql(sql: str | None, commands: tuple[str, ...]) -> tuple[str, ...]:
    return ((sql,) if sql else ()) + commands


__all__ = ["SnowflakeAccessResult", "access_steps", "apply_snowflake_access"]
