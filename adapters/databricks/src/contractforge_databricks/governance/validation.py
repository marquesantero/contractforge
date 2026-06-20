"""Databricks governance validation and access drift helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.coercion import mapping, mapping_list, string_list
from contractforge_databricks.rendering.names import target_full_name


def governance_referenced_columns(contract: SemanticContract) -> dict[str, list[str]]:
    annotations = contract.governance.annotations if contract.governance else None
    access = contract.governance.access if contract.governance else None
    annotation_columns = sorted(mapping(annotations).get("columns", {}).keys())
    row_filter_columns = sorted(
        {
            column
            for row_filter in mapping_list(mapping(access).get("row_filters"))
            for column in string_list(row_filter.get("columns"))
        }
    )
    mask_columns = sorted(
        {
            column
            for mask in mapping_list(mapping(access).get("column_masks"))
            for column in [str(mask.get("column")), *string_list(mask.get("using_columns"))]
            if column and column != "None"
        }
    )
    all_columns = sorted(set(annotation_columns) | set(row_filter_columns) | set(mask_columns))
    return {
        "annotations": annotation_columns,
        "row_filters": row_filter_columns,
        "column_masks": mask_columns,
        "all": all_columns,
    }


def validate_governance_contract(
    contract: SemanticContract,
    *,
    existing_columns: set[str] | list[str] | tuple[str, ...],
    target_table: str | None = None,
) -> dict[str, Any]:
    references = governance_referenced_columns(contract)
    columns = set(str(column) for column in existing_columns)
    issues = []
    annotations = mapping(contract.governance.annotations if contract.governance else None)
    table = mapping(annotations.get("table"))
    annotation_columns = mapping(annotations.get("columns"))
    contains_pii = str(mapping(table.get("tags")).get("contains_pii", "")).lower() == "true"
    pii_columns = sorted(
        column
        for column, config in annotation_columns.items()
        if bool(mapping(mapping(config).get("pii")).get("enabled", False))
    )
    if contains_pii and not pii_columns:
        issues.append(_issue("fail", "annotations", "table.tags.contains_pii", "contains_pii=true requires at least one column with pii.enabled=true"))
    for column in pii_columns:
        if not mapping(annotation_columns.get(column)).get("description"):
            issues.append(_issue("warn", "annotations", column, f"PII column {column!r} should declare a description"))

    for scope, referenced in references.items():
        if scope == "all":
            continue
        for column in sorted(set(referenced) - columns):
            issues.append(_issue("fail", scope, column, f"Column {column!r} referenced by {scope} does not exist"))
    return {
        "status": "FAILED" if any(issue["severity"] == "fail" for issue in issues) else "SUCCESS",
        "target_table": target_table or target_full_name(contract),
        "references": references,
        "issues": issues,
    }


def access_drift_report(
    contract: SemanticContract,
    *,
    current_grants: set[tuple[str, str]],
    target_table: str | None = None,
) -> dict[str, Any]:
    access = mapping(contract.governance.access if contract.governance else None)
    if not access:
        return _drift_payload("NOT_CONFIGURED", target_table or target_full_name(contract), set(), current_grants, [], [])
    declared = {
        (str(grant.get("principal")), str(privilege).upper())
        for grant in mapping_list(access.get("grants"))
        for privilege in string_list(grant.get("privileges"))
    }
    normalized_current = {(str(principal), str(privilege).upper()) for principal, privilege in current_grants}
    missing = sorted(declared - normalized_current)
    unmanaged = sorted(normalized_current - declared)
    policy = _access_policy(access)
    revoke_unmanaged = bool(mapping(access.get("access_policy")).get("revoke_unmanaged", access.get("revoke_unmanaged", False)))
    issues = [
        _issue(policy, "grant", f"{principal}:{privilege}", f"Declared grant is missing: {privilege} for {principal}")
        for principal, privilege in missing
    ]
    if revoke_unmanaged:
        issues.extend(
            _issue(policy, "grant", f"{principal}:{privilege}", f"Current unmanaged grant was detected: {privilege} from {principal}")
            for principal, privilege in unmanaged
        )
    status = "DRIFTED" if missing or (revoke_unmanaged and unmanaged) else "IN_SYNC"
    return _drift_payload(status, target_table or target_full_name(contract), declared, normalized_current, missing, unmanaged, issues)


def _drift_payload(
    status: str,
    target_table: str,
    declared: set[tuple[str, str]],
    current: set[tuple[str, str]],
    missing: list[tuple[str, str]],
    unmanaged: list[tuple[str, str]],
    issues: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "target_table": target_table,
        "declared_grants": sorted(declared),
        "current_grants": sorted(current),
        "missing_grants": missing,
        "unmanaged_grants": unmanaged,
        "issues": issues or [],
    }


def _access_policy(access: dict[str, Any]) -> str:
    policy = mapping(access.get("access_policy"))
    return "fail" if policy.get("on_drift", access.get("on_drift", "warn")) == "fail" else "warn"


def _issue(severity: str, scope: str, obj: str, message: str) -> dict[str, str]:
    return {"severity": severity, "scope": scope, "object": obj, "message": message}
