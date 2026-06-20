"""Render Unity Catalog access steps and audit SQL."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.coercion import string_list
from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_identifier, quote_table_name, sql_string


def access_steps(contract: SemanticContract) -> list[dict[str, Any]]:
    governance = contract.governance
    access = governance.access if governance else None
    if not isinstance(access, dict):
        return []
    target = target_full_name(contract)
    quoted_target = quote_table_name(target)
    steps: list[dict[str, Any]] = []
    for grant in access.get("grants", []):
        principal = str(grant["principal"])
        for privilege in string_list(grant.get("privileges")):
            steps.append(_grant_step(quoted_target, target, principal, privilege, access))
    for row_filter in access.get("row_filters", []):
        steps.append(_row_filter_step(quoted_target, row_filter, access))
    for column_mask in access.get("column_masks", []):
        steps.append(_column_mask_step(quoted_target, column_mask, access))
    return steps


def revoke_grant_steps(contract: SemanticContract, unmanaged_grants: list[tuple[str, str]]) -> list[dict[str, Any]]:
    access = contract.governance.access if contract.governance else None
    if not isinstance(access, dict):
        return []
    target = target_full_name(contract)
    quoted_target = quote_table_name(target)
    return [_revoke_step(quoted_target, target, principal, privilege, access) for principal, privilege in unmanaged_grants]


def render_access_sql(contract: SemanticContract) -> str:
    return "\n".join(f"{step['sql']};" for step in access_steps(contract))


def render_access_audit_insert_sql(
    contract: SemanticContract,
    *,
    run_id: str = "${run_id}",
    status: str = "PLANNED",
    captured_at_utc: datetime | None = None,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    steps = access_steps(contract)
    if not steps:
        return "-- No access intent declared.\n"
    table = evidence_table_names(catalog, schema)["access"]
    captured_at_utc = captured_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    statements = [
        _audit_insert(table, run_id, target_full_name(contract), step, status, captured_at_utc)
        for step in steps
    ]
    return ";\n".join(statements) + ";\n"


def _grant_step(
    quoted_target: str,
    target: str,
    principal: str,
    privilege: str,
    access: dict[str, Any],
) -> dict[str, Any]:
    return {
        "access_type": "grant",
        "principal": principal,
        "privilege": privilege,
        "column_name": None,
        "function_name": None,
        "object_name": target,
        "new_value": "GRANTED",
        "mode": _access_policy(access, "mode", "apply"),
        "drift_policy": _access_policy(access, "on_drift", "warn"),
        "revoke_unmanaged": _access_policy(access, "revoke_unmanaged", False),
        "sql": f"GRANT {privilege} ON TABLE {quoted_target} TO {_principal(principal)}",
    }


def _row_filter_step(quoted_target: str, row_filter: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]:
    columns = ", ".join(quote_identifier(column) for column in string_list(row_filter.get("columns")))
    function = str(row_filter["function"])
    return {
        "access_type": "row_filter",
        "principal": "|".join(string_list(row_filter.get("applies_to", {}).get("principals"))),
        "privilege": "ROW_FILTER",
        "column_name": "|".join(string_list(row_filter.get("columns"))),
        "function_name": function,
        "object_name": row_filter.get("name"),
        "new_value": function,
        "mode": _access_policy(access, "mode", "apply"),
        "drift_policy": _access_policy(access, "on_drift", "warn"),
        "revoke_unmanaged": _access_policy(access, "revoke_unmanaged", False),
        "sql": f"ALTER TABLE {quoted_target} SET ROW FILTER {function} ON ({columns})",
    }


def _column_mask_step(quoted_target: str, column_mask: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]:
    column = str(column_mask["column"])
    using_columns = string_list(column_mask.get("using_columns"))
    using_sql = ""
    if using_columns:
        using_sql = " USING COLUMNS (" + ", ".join(quote_identifier(item) for item in using_columns) + ")"
    function = str(column_mask["function"])
    return {
        "access_type": "column_mask",
        "principal": "|".join(string_list(column_mask.get("applies_to", {}).get("principals"))),
        "privilege": "COLUMN_MASK",
        "column_name": column,
        "function_name": function,
        "object_name": column,
        "new_value": function,
        "mode": _access_policy(access, "mode", "apply"),
        "drift_policy": _access_policy(access, "on_drift", "warn"),
        "revoke_unmanaged": _access_policy(access, "revoke_unmanaged", False),
        "sql": f"ALTER TABLE {quoted_target} ALTER COLUMN {quote_identifier(column)} SET MASK {function}{using_sql}",
    }


def _revoke_step(
    quoted_target: str,
    target: str,
    principal: str,
    privilege: str,
    access: dict[str, Any],
) -> dict[str, Any]:
    return {
        "access_type": "revoke",
        "principal": principal,
        "privilege": privilege,
        "column_name": None,
        "function_name": None,
        "object_name": target,
        "previous_value": "GRANTED",
        "new_value": "REVOKED",
        "mode": _access_policy(access, "mode", "apply"),
        "drift_policy": _access_policy(access, "on_drift", "warn"),
        "revoke_unmanaged": True,
        "sql": f"REVOKE {privilege} ON TABLE {quoted_target} FROM {_principal(principal)}",
    }


def _audit_insert(table: str, run_id: str, target: str, step: dict[str, Any], status: str, captured_at_utc: datetime) -> str:
    payload = json.dumps(step, sort_keys=True, separators=(",", ":"))
    columns = "run_id, target_table, action, status, payload_json, applied_at_utc, access_type, principal, privilege, column_name, function_name, object_name, applied_sql, new_value, mode, drift_policy, revoke_unmanaged"
    values = [
        sql_string(run_id),
        sql_string(target),
        sql_string(step["access_type"]),
        sql_string(status),
        sql_string(payload),
        f"TIMESTAMP {sql_string(captured_at_utc.strftime('%Y-%m-%d %H:%M:%S'))}",
        sql_string(step["access_type"]),
        sql_string(step.get("principal")),
        sql_string(step.get("privilege")),
        sql_string(step.get("column_name")),
        sql_string(step.get("function_name")),
        sql_string(step.get("object_name")),
        sql_string(step.get("sql")),
        sql_string(step.get("new_value")),
        sql_string(step.get("mode")),
        sql_string(step.get("drift_policy")),
        "true" if bool(step.get("revoke_unmanaged")) else "false",
    ]
    return f"INSERT INTO {quote_table_name(table)} ({columns}) VALUES ({', '.join(values)})"


def _access_policy(access: dict[str, Any], key: str, default: object) -> object:
    policy = access.get("access_policy", {})
    return policy.get(key, access.get(key, default)) if isinstance(policy, dict) else access.get(key, default)


def _principal(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"
