"""Lake Formation smoke permission checks."""

from __future__ import annotations

from typing import Any


def permission_blockers(findings: dict[str, Any]) -> list[str]:
    permissions = findings["lakeformation_table_permissions"].get("permissions") or []
    consumer = findings["consumer_principal"].get("principal")
    blockers: list[str] = []
    if has_broad_table_access(permissions, principal="IAM_ALLOWED_PRINCIPALS"):
        blockers.append(
            "IAM_ALLOWED_PRINCIPALS has broad table access; denied principals can bypass Lake Formation filters."
        )
    if consumer and has_broad_table_access(permissions, principal=consumer):
        blockers.append("Consumer principal has unfiltered table SELECT/ALL access; use DataCellsFilter SELECT only.")
    return blockers


def has_broad_table_access(permissions: list[dict[str, Any]], *, principal: str) -> bool:
    broad = {"ALL", "SELECT"}
    for entry in permissions:
        identifier = (entry.get("Principal") or {}).get("DataLakePrincipalIdentifier")
        if identifier != principal:
            continue
        resource = entry.get("Resource") or {}
        if "Table" not in resource and "TableWithColumns" not in resource:
            continue
        granted = {str(item).upper() for item in entry.get("Permissions") or []}
        if granted & broad:
            return True
    return False


__all__ = ["has_broad_table_access", "permission_blockers"]
