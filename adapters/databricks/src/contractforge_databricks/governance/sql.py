"""Render reviewable Unity Catalog governance SQL."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.annotations import render_annotations_sql
from contractforge_databricks.governance.access import render_access_sql
from contractforge_databricks.rendering.names import target_full_name


def render_governance_sql(contract: SemanticContract) -> str:
    governance = contract.governance
    if governance is None:
        return "-- No governance intent declared.\n"

    target = target_full_name(contract)
    lines = [
        "-- Review before execution. Function names and privileges are contract-owned.",
        f"-- Target: {target}",
        "",
    ]
    if governance.owner:
        lines.append(f"-- Owner intent: {governance.owner}")
    access_sql_body = render_access_sql(contract)
    if access_sql_body:
        lines.append(access_sql_body)
    access_sql = "\n".join(lines) + "\n"
    annotations_sql = render_annotations_sql(contract)
    if annotations_sql.startswith("-- No annotations intent declared."):
        return access_sql
    return annotations_sql + "\n" + access_sql
