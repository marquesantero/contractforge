"""Consolidated BigQuery governance ledger planning artifacts."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.governance.annotations import annotations_plan
from contractforge_gcp.governance.policy_tags import policy_tags_plan
from contractforge_gcp.rendering.names import evidence_dataset, identifier, table_prefix, target_table_id
from contractforge_gcp.runtime import BigQueryJobEvidence


def has_governance_ledger_plan(contract: SemanticContract) -> bool:
    return bool(contract.governance and (contract.governance.access or contract.governance.annotations))


def render_bigquery_governance_ledger_plan(contract: SemanticContract, environment: GCPEnvironment) -> str:
    if not has_governance_ledger_plan(contract):
        return ""
    payload = governance_ledger_plan(contract, environment)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_bigquery_governance_evidence_insert_sql(
    *,
    contract: SemanticContract,
    environment: GCPEnvironment,
    job: BigQueryJobEvidence,
) -> str:
    """Render governance evidence rows from the deterministic ledger plan."""

    if not has_governance_ledger_plan(contract):
        return "-- No governance ledger intent declared.\n"
    rows = _governance_evidence_rows(contract, environment, job)
    if not rows:
        return "-- No governance ledger actions declared.\n"
    table = f"`{table_prefix(environment.project_id, evidence_dataset(contract, environment))}.contractforge_governance_evidence`"
    return _insert_many(table, rows)


def governance_ledger_plan(contract: SemanticContract, environment: GCPEnvironment) -> dict[str, Any]:
    actions = _governance_actions(contract, environment)
    review_required = [action for action in actions if action["status"] in {"REVIEW_REQUIRED", "PLANNED_REVIEW_REQUIRED"}]
    return {
        "kind": "contractforge.gcp.bigquery_governance_ledger_plan.v1",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "target": target_table_id(contract, environment),
        "status": "PLANNED_WITH_REVIEW_BOUNDARIES" if review_required else "PLANNED",
        "evidence": {
            "dataset": evidence_dataset(contract, environment),
            "table": "contractforge_governance_evidence",
            "table_ref": f"{table_prefix(environment.project_id, evidence_dataset(contract, environment))}.contractforge_governance_evidence",
        },
        "actions": actions,
        "review_required": review_required,
        "review_boundaries": [
            "This ledger is a deterministic planning artifact and does not apply governance changes.",
            "Row access policies, direct data policies, policy tags and descriptions have separate smoke evidence.",
            "Drift reconciliation, overwrite-retention behavior and tag-based masking are not certified in this artifact.",
        ],
    }


def _governance_evidence_rows(
    contract: SemanticContract,
    environment: GCPEnvironment,
    job: BigQueryJobEvidence,
) -> list[dict[str, Any]]:
    return [
        {
            "run_id": job.job_id or "untracked_bigquery_job",
            "contract_name": contract.target.name,
            "target_table": target_table_id(contract, environment),
            "governance_surface": action["surface"],
            "operation": action["operation"],
            "subject": _subject(action),
            "status": action["status"],
            "details_json": json.dumps(_redact_governance_value(action), sort_keys=True, separators=(",", ":")),
            "evidence_ts": _timestamp_literal(job.finished_at_ms) or "CURRENT_TIMESTAMP()",
            "error_message": action.get("reason") if action["status"] in {"REVIEW_REQUIRED", "PLANNED_REVIEW_REQUIRED"} else None,
        }
        for action in governance_ledger_plan(contract, environment)["actions"]
    ]


def _governance_actions(contract: SemanticContract, environment: GCPEnvironment) -> list[dict[str, Any]]:
    access = contract.governance.access if contract.governance and isinstance(contract.governance.access, dict) else {}
    actions: list[dict[str, Any]] = []
    actions.extend(_row_filter_actions(access))
    actions.extend(_column_mask_actions(access))
    actions.extend(_grant_actions(access))
    actions.extend(_annotation_actions(contract, environment))
    actions.extend(_policy_tag_actions(contract, environment))
    return actions


def _row_filter_actions(access: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in access.get("row_filters", ()):
        row_filter = _mapping(item)
        name = str(row_filter.get("name") or row_filter.get("function") or "").strip()
        principals = _principals(row_filter)
        actions.append(
            {
                "surface": "bigquery_row_access_policy",
                "operation": "apply_or_validate",
                "name": name or "row_filter",
                "filter_expression": str(row_filter.get("function") or "").strip(),
                "status": "PLANNED_REVIEW_REQUIRED",
                "columns": _string_list(row_filter.get("columns")),
                "principals": principals,
                "reason": "Row access policy DDL/enforcement is validated in smoke tests; per-contract drift and overwrite retention still require review.",
            }
        )
    return actions


def _column_mask_actions(access: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in _column_masks(access):
        column = str(item.get("column") or "").strip()
        function = str(item.get("function") or "").strip()
        if function.startswith("policy_tag:") and "/policyTags/" in function:
            continue
        status = "PLANNED_REVIEW_REQUIRED" if function else "REVIEW_REQUIRED"
        actions.append(
            {
                "surface": "bigquery_data_policy",
                "operation": "apply_or_validate",
                "name": column or "column_mask",
                "column": column,
                "function": function,
                "principals": _principals(item),
                "status": status,
                "reason": "Direct column data masking has smoke evidence; function mapping, IAM and drift behavior remain contract-specific review items.",
            }
        )
    return actions


def _grant_actions(access: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in access.get("grants", ()):
        grant = _mapping(item)
        actions.append(
            {
                "surface": "bigquery_iam",
                "operation": "grant",
                "principal": str(grant.get("principal") or "").strip(),
                "privileges": _string_list(grant.get("privileges")),
                "status": "REVIEW_REQUIRED",
                "reason": "IAM grants need least-privilege mapping to Google Cloud roles before apply.",
            }
        )
    return actions


def _annotation_actions(contract: SemanticContract, environment: GCPEnvironment) -> list[dict[str, Any]]:
    plan = annotations_plan(contract, environment)
    actions = [
        {
            "surface": "bigquery_description",
            "operation": "apply",
            "scope": change["annotation_scope"],
            "column": change["column_name"],
            "key": change["key"],
            "value": change["value"],
            "status": change["status"],
        }
        for change in plan.get("changes", ())
    ]
    actions.extend(
        {
            "surface": "knowledge_catalog_or_dataplex_aspect",
            "operation": "review",
            "scope": item["annotation_scope"],
            "column": item["column_name"],
            "annotation_type": item["annotation_type"],
            "status": item["status"],
            "reason": item["reason"],
        }
        for item in plan.get("review_required", ())
    )
    return actions


def _policy_tag_actions(contract: SemanticContract, environment: GCPEnvironment) -> list[dict[str, Any]]:
    plan = policy_tags_plan(contract, environment)
    return [
        {
            "surface": "data_catalog_policy_tag",
            "operation": "schema_update",
            "column": change["column_name"],
            "policy_tag": change["policy_tag"],
            "status": change["status"],
        }
        for change in plan.get("changes", ())
    ]


def _column_masks(access: dict[str, Any]) -> list[dict[str, Any]]:
    value = access.get("column_masks")
    if isinstance(value, dict):
        return [{**_mapping(config), "column": column} for column, config in value.items()]
    if isinstance(value, list):
        return [_mapping(item) for item in value]
    return []


def _principals(item: dict[str, Any]) -> list[str]:
    applies_to = _mapping(item.get("applies_to"))
    return _string_list(applies_to.get("principals"))


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = [value] if isinstance(value, str) else list(value)
    return [str(item).strip() for item in values if str(item).strip()]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _subject(action: dict[str, Any]) -> str | None:
    for key in ("name", "column", "principal", "scope"):
        value = action.get(key)
        if value not in (None, "", [], {}):
            return str(_redact_governance_value(value))
    return None


def _insert_many(table: str, rows: list[dict[str, Any]]) -> str:
    names = tuple(rows[0])
    columns = ", ".join(identifier(name) for name in names)
    values = ",\n  ".join("(" + ", ".join(_literal(row.get(name)) for name in names) + ")" for row in rows)
    return f"INSERT INTO {table} ({columns}) VALUES\n  {values};\n"


def _timestamp_literal(value: int | None) -> str | None:
    if value is None:
        return None
    return f"TIMESTAMP_MILLIS({value})"


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP {_string(value.strftime('%Y-%m-%d %H:%M:%S'))}"
    if isinstance(value, str) and (value.startswith("TIMESTAMP_MILLIS(") or value == "CURRENT_TIMESTAMP()"):
        return value
    return _string(str(redact_value(value)))


def _string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
        .replace("'", "\\'")
    )
    return "'" + escaped + "'"


def _redact_governance_value(value: Any) -> Any:
    redacted = redact_value(value)
    if isinstance(redacted, dict):
        return {key: _redact_governance_value(item) for key, item in redacted.items()}
    if isinstance(redacted, list):
        return [_redact_governance_value(item) for item in redacted]
    if isinstance(redacted, tuple):
        return tuple(_redact_governance_value(item) for item in redacted)
    if isinstance(redacted, str):
        return re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "REDACTED_EMAIL", redacted)
    return redacted
