"""Render Fabric access governance plans and evidence SQL."""

from __future__ import annotations

import json
from datetime import date, datetime
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_fabric.contract_extensions import fabric_extensions
from contractforge_fabric.evidence import evidence_table_names
from contractforge_fabric.naming import target_table_name
from contractforge_fabric.sql import quote_identifier, quote_table_name, sql_bool, sql_string

if TYPE_CHECKING:
    from contractforge_fabric.runtime.rest import FabricRestClient


@dataclass(frozen=True)
class FabricAccessApplyResult:
    action: str
    status: str
    details: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status == "SUCCEEDED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def has_access_intent(contract: SemanticContract) -> bool:
    return bool(access_steps(contract))


def render_access_plan(contract: SemanticContract) -> str:
    plan = access_plan(contract)
    if not plan["steps"]:
        return ""
    return json.dumps(plan, indent=2, sort_keys=True)


def access_plan(contract: SemanticContract) -> dict[str, Any]:
    steps = access_steps(contract)
    native_steps = native_access_apply_steps(contract)
    access = _access(contract)
    return {
        "adapter": "fabric",
        "target": target_table_name(contract),
        "status": "PLANNED" if steps or native_steps else "NOOP",
        "contract_mode": _access_policy(access, "mode", "apply") if access else None,
        "contract_drift_policy": _access_policy(access, "on_drift", "warn") if access else None,
        "contract_revoke_unmanaged": bool(_access_policy(access, "revoke_unmanaged", False)) if access else False,
        "apply_surface": "Fabric workspace role assignments, item sensitivity labels and review-only table policy evidence",
        "apply_mode": "hybrid" if native_steps else "review_only",
        "note": (
            "Fabric can apply explicit workspace role assignments and sensitivity labels "
            "when contract extensions provide Fabric-native IDs. Table grants, row filters "
            "and column masks remain review-only until the chosen Fabric/Purview policy "
            "surface is validated."
        ),
        "native_apply_steps": native_steps,
        "steps": steps,
    }


def native_access_apply_steps(contract: SemanticContract) -> list[dict[str, Any]]:
    """Return Fabric-native governance operations declared through extensions.fabric."""

    fabric = fabric_extensions(contract)
    apply_config = _mapping(fabric.get("access_apply") or fabric.get("governance_apply"))
    steps: list[dict[str, Any]] = []
    for assignment in _iter_mapping_items(apply_config.get("workspace_role_assignments")):
        principal = _mapping(assignment.get("principal"))
        principal_id = str(principal.get("id") or assignment.get("principal_id") or "").strip()
        principal_type = str(principal.get("type") or assignment.get("principal_type") or "").strip()
        role = str(assignment.get("role") or "").strip()
        if principal_id and principal_type and role:
            steps.append(
                {
                    "action": "apply_workspace_role_assignment",
                    "status": "PLANNED",
                    "principal": {"id": principal_id, "type": principal_type},
                    "role": role,
                    "mode": str(assignment.get("mode") or "upsert"),
                    "surface": "Fabric Core workspace roleAssignments API",
                }
            )
    for label in _iter_mapping_items(apply_config.get("sensitivity_labels")):
        label_id = str(label.get("label_id") or label.get("id") or "").strip()
        items = label.get("items")
        if label_id and isinstance(items, list) and items:
            steps.append(
                {
                    "action": "apply_sensitivity_label",
                    "status": "PLANNED",
                    "label_id": label_id,
                    "assignment_method": label.get("assignment_method") or "Standard",
                    "items": [dict(item) for item in items if isinstance(item, dict)],
                    "surface": "Fabric Admin bulkSetLabels API",
                }
            )
    for role in _iter_mapping_items(apply_config.get("onelake_data_access_roles")):
        item_id = str(role.get("item_id") or "").strip()
        name = str(role.get("name") or "").strip()
        decision_rules = role.get("decisionRules") or role.get("decision_rules")
        if item_id and name and isinstance(decision_rules, list) and decision_rules:
            payload = {
                "name": name,
                "kind": str(role.get("kind") or "Policy"),
                "decisionRules": [dict(rule) for rule in decision_rules if isinstance(rule, dict)],
            }
            members = role.get("members")
            if isinstance(members, dict):
                payload["members"] = dict(members)
            steps.append(
                {
                    "action": "apply_onelake_data_access_role",
                    "status": "PLANNED",
                    "item_id": item_id,
                    "role_name": name,
                    "role": payload,
                    "conflict_policy": str(role.get("conflict_policy") or "Overwrite"),
                    "preview": bool(role.get("preview", True)),
                    "delete_after_validation": bool(role.get("delete_after_validation", False)),
                    "surface": "Fabric OneLake dataAccessRoles preview API",
                }
            )
    return redact_value(steps)


def apply_native_access_governance(
    contract: SemanticContract,
    *,
    client: "FabricRestClient",
    dry_run: bool = True,
) -> list[FabricAccessApplyResult]:
    """Apply Fabric-native governance steps that are explicitly declared with IDs."""

    results: list[FabricAccessApplyResult] = []
    for step in native_access_apply_steps(contract):
        if dry_run:
            results.append(FabricAccessApplyResult(action=step["action"], status="PLANNED", details=step))
            continue
        if step["action"] == "apply_workspace_role_assignment":
            principal = _mapping(step.get("principal"))
            response = client.add_workspace_role_assignment(
                principal_id=str(principal["id"]),
                principal_type=str(principal["type"]),
                role=str(step["role"]),
            )
            results.append(
                FabricAccessApplyResult(
                    action=step["action"],
                    status="SUCCEEDED",
                    details={"request": step, "response": redact_value(response)},
                )
            )
        elif step["action"] == "apply_sensitivity_label":
            response = client.bulk_set_item_labels(
                items=[dict(item) for item in step.get("items", []) if isinstance(item, dict)],
                label_id=str(step["label_id"]),
                assignment_method=str(step.get("assignment_method") or "Standard"),
            )
            results.append(
                FabricAccessApplyResult(
                    action=step["action"],
                    status="SUCCEEDED",
                    details={"request": step, "response": redact_value(response)},
                )
            )
        elif step["action"] == "apply_onelake_data_access_role":
            response = client.create_or_update_onelake_data_access_role(
                item_id=str(step["item_id"]),
                role=_mapping(step.get("role")),
                conflict_policy=str(step.get("conflict_policy") or "Overwrite"),
                preview=bool(step.get("preview", True)),
            )
            listed_roles = client.list_onelake_data_access_roles(item_id=str(step["item_id"]))
            details = {
                "request": step,
                "response": redact_value(response),
                "listed": any(
                    str(role.get("name") or "") == str(step["role_name"])
                    for role in listed_roles
                ),
            }
            if step.get("delete_after_validation"):
                client.delete_onelake_data_access_role(
                    item_id=str(step["item_id"]),
                    role_name=str(step["role_name"]),
                    preview=bool(step.get("preview", True)),
                )
                details["deleted_after_validation"] = True
            results.append(
                FabricAccessApplyResult(
                    action=step["action"],
                    status="SUCCEEDED",
                    details=redact_value(details),
                )
            )
    return results


def access_steps(contract: SemanticContract) -> list[dict[str, Any]]:
    access = _access(contract)
    if not access:
        return []
    target = target_table_name(contract)
    steps: list[dict[str, Any]] = []
    for grant in _iter_mapping_items(access.get("grants")):
        principal = str(grant.get("principal") or "").strip()
        for privilege in _as_list(grant.get("privileges")):
            if principal and privilege:
                steps.append(_grant_step(target, access, principal=principal, privilege=privilege))
    for row_filter in _iter_mapping_items(access.get("row_filters")):
        steps.append(_row_filter_step(target, access, row_filter))
    for column_mask in _iter_column_masks(access.get("column_masks")):
        steps.append(_column_mask_step(target, access, column_mask))
    return steps


def render_access_evidence_sql(
    contract: SemanticContract,
    *,
    schema: str = "contractforge",
    run_id: str = "${run_id}",
    status: str = "PLANNED",
    captured_at_utc: datetime | None = None,
) -> str:
    rows = _access_evidence_rows(contract, run_id=run_id, status=status, captured_at_utc=captured_at_utc)
    if not rows:
        return "-- No access intent declared.\n"
    table = quote_table_name(evidence_table_names(schema)["access"])
    return "\n".join(_insert(table, row) for row in rows) + "\n"


def _grant_step(target: str, access: dict[str, Any], *, principal: str, privilege: str) -> dict[str, Any]:
    privilege_name = str(privilege).strip().replace("_", " ").upper()
    return _step(
        access,
        action="plan_grant",
        access_type="grant",
        principal=principal,
        privilege=privilege_name,
        column_name=None,
        function_name=None,
        object_name=target,
        new_value="GRANTED",
        planned_statement=f"GRANT {privilege_name} ON TABLE {target} TO {principal}",
    )


def _row_filter_step(target: str, access: dict[str, Any], row_filter: dict[str, Any]) -> dict[str, Any]:
    columns = _as_list(row_filter.get("columns"))
    function = str(row_filter.get("function") or "").strip()
    principals = "|".join(_as_list(_mapping(row_filter.get("applies_to")).get("principals")))
    return _step(
        access,
        action="plan_row_filter",
        access_type="row_filter",
        principal=principals or None,
        privilege="ROW_FILTER",
        column_name="|".join(columns) or None,
        function_name=function or None,
        object_name=str(row_filter.get("name") or target),
        new_value=function or None,
        planned_statement=f"APPLY ROW FILTER {function} ON {target} ({', '.join(columns)})",
    )


def _column_mask_step(target: str, access: dict[str, Any], column_mask: dict[str, Any]) -> dict[str, Any]:
    column = str(column_mask.get("column") or "").strip()
    function = str(column_mask.get("function") or "").strip()
    using_columns = _as_list(column_mask.get("using_columns"))
    principals = "|".join(_as_list(_mapping(column_mask.get("applies_to")).get("principals")))
    using = f" USING ({', '.join(using_columns)})" if using_columns else ""
    return _step(
        access,
        action="plan_column_mask",
        access_type="column_mask",
        principal=principals or None,
        privilege="COLUMN_MASK",
        column_name=column or None,
        function_name=function or None,
        object_name=target,
        new_value=function or None,
        planned_statement=f"APPLY COLUMN MASK {function} ON {target}.{column}{using}",
    )


def _step(
    access: dict[str, Any],
    *,
    action: str,
    access_type: str,
    principal: str | None,
    privilege: str | None,
    column_name: str | None,
    function_name: str | None,
    object_name: str,
    new_value: str | None,
    planned_statement: str,
) -> dict[str, Any]:
    return redact_value(
        {
            "action": action,
            "access_type": access_type,
            "principal": principal,
            "privilege": privilege,
            "column_name": column_name,
            "function_name": function_name,
            "object_name": object_name,
            "status": "PLANNED",
            "mode": _access_policy(access, "mode", "apply"),
            "drift_policy": _access_policy(access, "on_drift", "warn"),
            "revoke_unmanaged": bool(_access_policy(access, "revoke_unmanaged", False)),
            "previous_value": None,
            "new_value": new_value,
            "applied_sql": "fabric_access_review_plan",
            "planned_statement": planned_statement,
        }
    )


def _access_evidence_rows(
    contract: SemanticContract,
    *,
    run_id: str,
    status: str,
    captured_at_utc: datetime | None,
) -> list[dict[str, Any]]:
    captured = captured_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    target = target_table_name(contract)
    return [_access_evidence_row(step, run_id=run_id, target=target, status=status, captured=captured) for step in access_steps(contract)]


def _access_evidence_row(
    step: dict[str, Any],
    *,
    run_id: str,
    target: str,
    status: str,
    captured: datetime,
) -> dict[str, Any]:
    payload = {key: value for key, value in step.items() if key != "planned_statement"}
    return {
        "access_run_id": f"{run_id}:{step['action']}:{step.get('principal') or step.get('column_name') or step['access_type']}",
        "run_id": run_id,
        "target_table": target,
        "action": step["action"],
        "access_type": step["access_type"],
        "principal": step.get("principal"),
        "privilege": step.get("privilege"),
        "column_name": step.get("column_name"),
        "function_name": step.get("function_name"),
        "object_name": step.get("object_name"),
        "status": status,
        "error_message": None,
        "applied_sql": step.get("applied_sql"),
        "previous_value": step.get("previous_value"),
        "new_value": step.get("new_value"),
        "mode": step.get("mode"),
        "drift_policy": step.get("drift_policy"),
        "revoke_unmanaged": bool(step.get("revoke_unmanaged")),
        "access_ts_utc": captured,
        "access_date": captured.date(),
        "payload_json": json.dumps(redact_value(payload), sort_keys=True, separators=(",", ":")),
        "applied_at_utc": captured,
        "framework_version": "contractforge-fabric",
        "ctrl_schema_version": 1,
    }


def _access(contract: SemanticContract) -> dict[str, Any] | None:
    access = contract.governance.access if contract.governance else None
    return dict(access) if isinstance(access, dict) else None


def _access_policy(access: dict[str, Any], key: str, default: object) -> object:
    policy = _mapping(access.get("access_policy"))
    return policy.get(key, access.get(key, default))


def _iter_mapping_items(value: object) -> tuple[dict[str, Any], ...]:
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


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]  # type: ignore[union-attr]


def _insert(table: str, columns: dict[str, Any]) -> str:
    names = ", ".join(quote_identifier(name) for name in columns)
    values = ", ".join(_literal(value) for value in columns.values())
    return f"INSERT INTO {table} ({names}) VALUES ({values});"


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return sql_bool(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP {sql_string(value.strftime('%Y-%m-%d %H:%M:%S'))}"
    if isinstance(value, date):
        return f"DATE {sql_string(value.strftime('%Y-%m-%d'))}"
    return sql_string(redact_value(str(value)))
