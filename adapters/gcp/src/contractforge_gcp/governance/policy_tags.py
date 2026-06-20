"""Render BigQuery policy-tag governance plans."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import target_table_id


def has_policy_tag_access(contract: SemanticContract) -> bool:
    return bool(policy_tag_steps(contract))


def render_bigquery_policy_tags_plan(contract: SemanticContract, environment: GCPEnvironment) -> str:
    plan = policy_tags_plan(contract, environment)
    if not plan["changes"]:
        return ""
    return json.dumps(plan, indent=2, sort_keys=True)


def policy_tags_plan(contract: SemanticContract, environment: GCPEnvironment) -> dict[str, Any]:
    changes = policy_tag_steps(contract)
    return {
        "adapter": "gcp",
        "target": target_table_id(contract, environment),
        "status": "PLANNED" if changes else "NOOP",
        "apply_surface": "BigQuery schema update with Data Catalog policyTags",
        "apply_mode": "schema_update",
        "note": "BigQuery policy tags must be merged into the current table schema before applying a schema update.",
        "changes": changes,
    }


def policy_tag_steps(contract: SemanticContract) -> list[dict[str, Any]]:
    access = contract.governance.access if contract.governance and isinstance(contract.governance.access, dict) else {}
    rows = []
    for mask in _column_masks(access):
        column = str(mask.get("column") or "").strip()
        policy_tag = _policy_tag_resource(mask.get("function"))
        if column and policy_tag:
            rows.append(
                {
                    "access_scope": "column",
                    "access_type": "policy_tag",
                    "column_name": column,
                    "policy_tag": policy_tag,
                    "status": "PLANNED",
                }
            )
    return rows


def _column_masks(access: dict[str, Any]) -> list[dict[str, Any]]:
    value = access.get("column_masks")
    if isinstance(value, dict):
        return [{**_mapping(config), "column": column} for column, config in value.items()]
    if isinstance(value, list):
        return [_mapping(item) for item in value]
    return []


def _policy_tag_resource(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("policy_tag:"):
        text = text.removeprefix("policy_tag:").strip()
    if "/policyTags/" not in text:
        return ""
    return text


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
