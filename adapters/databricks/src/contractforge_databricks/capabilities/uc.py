"""Unity Catalog capability issue helpers."""

from __future__ import annotations

from typing import Any, Iterable

from contractforge_databricks.capabilities.evaluate import evaluate_databricks_capabilities
from contractforge_databricks.capabilities.models import DatabricksCapabilities

UC_CAPABILITY_ALIASES = {
    "table_comments": "uc_table_comments",
    "column_comments": "uc_column_comments",
    "table_tags": "uc_table_tags",
    "column_tags": "uc_column_tags",
    "grants": "uc_grants",
    "row_filters": "uc_row_filters",
    "column_masks": "uc_column_masks",
}


def uc_capability_issues(
    target_table: str,
    requirements: Iterable[tuple[str, str, str, str]],
    *,
    capabilities: DatabricksCapabilities | None = None,
    runtime_type: str | None = "serverless",
) -> list[dict[str, Any]]:
    caps = capabilities or evaluate_databricks_capabilities(target_table=target_table, runtime_type=runtime_type)
    issues = []
    for capability, scope, obj, severity in requirements:
        native_name = UC_CAPABILITY_ALIASES.get(capability, capability)
        if caps.supports(native_name):
            continue
        issues.append(
            {
                "severity": severity,
                "scope": scope,
                "object": obj,
                "capability": native_name,
                "status": caps.status(native_name),
                "message": (
                    f"{native_name} is not supported for {target_table}. "
                    "Use a three-part Unity Catalog table or remove the feature from the contract."
                ),
            }
        )
    return issues
