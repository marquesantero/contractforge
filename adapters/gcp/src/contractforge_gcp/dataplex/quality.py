"""Render Dataplex data-quality DataScan planning artifacts.

The GCP stable surface executes quality through BigQuery SQL today. This module
renders deterministic Dataplex REST payloads for review and later native
execution/readback validation; it does not run Dataplex jobs.
"""

from __future__ import annotations

import json
import re
from typing import Any

from contractforge_core.semantic import QualityIntent, SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import evidence_dataset, target_dataset, target_project


def has_dataplex_quality_plan(contract: SemanticContract) -> bool:
    """Return true when the contract has quality intent worth planning for Dataplex."""

    return bool(contract.quality)


def render_dataplex_data_quality_plan(contract: SemanticContract, env: GCPEnvironment) -> str:
    """Render a deterministic Dataplex DataScan create request for review."""

    if not has_dataplex_quality_plan(contract):
        return ""
    project = target_project(contract, env) or env.project_id or "UNSPECIFIED_PROJECT"
    location = _dataplex_location(env)
    dataset = target_dataset(contract, env)
    table = contract.target.name
    mapped_rules: list[dict[str, Any]] = []
    review_required_rules: list[dict[str, str]] = []
    for rule in contract.quality:
        mapped = _map_quality_rule(rule)
        if mapped:
            mapped_rules.extend(mapped)
        else:
            review_required_rules.append(
                {
                    "name": rule.name,
                    "rule": rule.rule,
                    "reason": _review_reason(rule),
                }
            )
    payload = {
        "kind": "contractforge.gcp.dataplex_data_quality_plan.v1",
        "status": "PLANNED_REVIEW_REQUIRED",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "execution": {
            "included": False,
            "reason": (
                "This artifact is a deterministic Dataplex DataScan REST plan. "
                "Native DataScan execution, result export readback and lineage readback "
                "remain outside the current stable GCP surface."
            ),
        },
        "target": {
            "project_id": project,
            "location": location,
            "dataset": dataset,
            "table": table,
            "bigquery_resource": _bigquery_resource(project, dataset, table),
        },
        "create_request": {
            "parent": f"projects/{project}/locations/{location}",
            "dataScanId": _data_scan_id(dataset, table),
            "dataScan": {
                "displayName": f"ContractForge {dataset}.{table} data quality",
                "data": {"resource": _bigquery_resource(project, dataset, table)},
                "dataQualitySpec": {
                    "rules": mapped_rules,
                    "catalogPublishingEnabled": False,
                    "postScanActions": {
                        "bigqueryExport": {
                            "resultsTable": _results_table(project, evidence_dataset(contract, env)),
                        }
                    },
                },
            },
        },
        "mapped_rules": [
            {
                "name": rule["name"],
                "dimension": rule.get("dimension"),
                "type": _rule_type(rule),
                "column": rule.get("column"),
            }
            for rule in mapped_rules
        ],
        "review_required_rules": review_required_rules,
        "rest_hints": {
            "create": "POST https://dataplex.googleapis.com/v1/{parent}/dataScans?dataScanId={dataScanId}",
            "run": "POST https://dataplex.googleapis.com/v1/{name}:run",
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_dataplex_data_quality_execution_plan(contract: SemanticContract, env: GCPEnvironment) -> str:
    """Render deterministic Dataplex DataScan command/readback metadata."""

    plan_body = render_dataplex_data_quality_plan(contract, env)
    if not plan_body:
        return ""
    plan = json.loads(plan_body)
    create_request = plan["create_request"]
    parent = str(create_request["parent"])
    data_scan_id = str(create_request["dataScanId"])
    data_scan_name = f"{parent}/dataScans/{data_scan_id}"
    result_table = str(
        create_request["dataScan"]["dataQualitySpec"]["postScanActions"]["bigqueryExport"]["resultsTable"]
    )
    result_table_sql = _results_table_sql(result_table)
    payload = {
        "kind": "contractforge.gcp.dataplex_data_quality_execution_plan.v1",
        "status": "PLANNED_REVIEW_REQUIRED",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "execution": {
            "included": False,
            "reason": (
                "Adapter-owned Dataplex command and readback metadata is generated, "
                "but native DataScan execution/readback still needs real-account evidence."
            ),
        },
        "data_scan": {
            "name": data_scan_name,
            "parent": parent,
            "id": data_scan_id,
            "location": plan["target"]["location"],
            "result_table": result_table,
        },
        "rest": {
            "create": {
                "method": "POST",
                "url": f"https://dataplex.googleapis.com/v1/{parent}/dataScans?dataScanId={data_scan_id}",
                "body": create_request["dataScan"],
            },
            "run": {
                "method": "POST",
                "url": f"https://dataplex.googleapis.com/v1/{data_scan_name}:run",
                "body": {},
            },
            "get_data_scan": {
                "method": "GET",
                "url": f"https://dataplex.googleapis.com/v1/{data_scan_name}",
            },
            "list_jobs": {
                "method": "GET",
                "url": f"https://dataplex.googleapis.com/v1/{data_scan_name}/jobs",
            },
            "get_job_template": {
                "method": "GET",
                "url": f"https://dataplex.googleapis.com/v1/{data_scan_name}/jobs/{{job_id}}",
            },
            "delete": {
                "method": "DELETE",
                "url": f"https://dataplex.googleapis.com/v1/{data_scan_name}",
            },
        },
        "curl_templates": {
            "auth_header": "Authorization: Bearer ${ACCESS_TOKEN}",
            "create": [
                "curl",
                "-X",
                "POST",
                "-H",
                "Authorization: Bearer ${ACCESS_TOKEN}",
                "-H",
                "Content-Type: application/json",
                "-d",
                "<dataScan JSON from rest.create.body>",
                f"https://dataplex.googleapis.com/v1/{parent}/dataScans?dataScanId={data_scan_id}",
            ],
            "run": [
                "curl",
                "-X",
                "POST",
                "-H",
                "Authorization: Bearer ${ACCESS_TOKEN}",
                "-H",
                "Content-Type: application/json",
                "-d",
                "{}",
                f"https://dataplex.googleapis.com/v1/{data_scan_name}:run",
            ],
            "list_jobs": [
                "curl",
                "-H",
                "Authorization: Bearer ${ACCESS_TOKEN}",
                f"https://dataplex.googleapis.com/v1/{data_scan_name}/jobs",
            ],
        },
        "readback": {
            "job_state_path": "jobs[].state",
            "latest_job_query_hint": "Use list_jobs, then call get_job_template with the selected job id.",
            "bigquery_export_query": f"SELECT * FROM `{result_table_sql}` LIMIT 100",
        },
        "review_boundaries": [
            "This artifact does not execute Dataplex jobs.",
            "Promotion requires live DataScan create/run/job readback and BigQuery export readback.",
            "Native Dataplex lineage event readback remains a separate promotion gate.",
        ],
        "sources": [
            "https://docs.cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.dataScans",
            "https://docs.cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.dataScans/run",
            "https://docs.cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.dataScans.jobs",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _map_quality_rule(rule: QualityIntent) -> list[dict[str, Any]]:
    if rule.rule == "not_null" and rule.columns:
        return [
            {
                "name": _rule_name(f"{column}_not_null"),
                "description": f"ContractForge not_null rule for {column}.",
                "column": column,
                "dimension": "COMPLETENESS",
                "threshold": 1.0,
                "nonNullExpectation": {},
            }
            for column in rule.columns
        ]
    if rule.rule == "unique_key" and len(rule.columns) == 1:
        column = rule.columns[0]
        return [
            {
                "name": _rule_name(rule.name),
                "description": f"ContractForge unique_key rule for {column}.",
                "column": column,
                "dimension": "UNIQUENESS",
                "threshold": 1.0,
                "uniquenessExpectation": {},
            }
        ]
    if rule.rule == "accepted_values" and rule.columns and isinstance(rule.value, (list, tuple, set)):
        column = rule.columns[0]
        return [
            {
                "name": _rule_name(rule.name),
                "description": f"ContractForge accepted_values rule for {column}.",
                "column": column,
                "dimension": "VALIDITY",
                "threshold": 1.0,
                "setExpectation": {"values": [str(value) for value in rule.value]},
            }
        ]
    if rule.rule == "row_count_minimum" and rule.value is not None:
        return [
            {
                "name": _rule_name(rule.name),
                "description": "ContractForge min_rows rule.",
                "dimension": "VOLUME",
                "threshold": 1.0,
                "tableConditionExpectation": {"sqlExpression": f"COUNT(*) >= {int(rule.value)}"},
            }
        ]
    if rule.rule == "max_null_ratio" and rule.columns and rule.value is not None:
        column = rule.columns[0]
        return [
            {
                "name": _rule_name(rule.name),
                "description": f"ContractForge max_null_ratio rule for {column}.",
                "column": column,
                "dimension": "COMPLETENESS",
                "threshold": max(0.0, min(1.0, 1.0 - float(rule.value))),
                "rowConditionExpectation": {"sqlExpression": f"`{column}` IS NOT NULL"},
            }
        ]
    if rule.rule == "expression" and rule.value:
        return [
            {
                "name": _rule_name(rule.name),
                "description": "ContractForge expression quality rule.",
                "dimension": "VALIDITY",
                "threshold": 1.0,
                "rowConditionExpectation": {"sqlExpression": str(rule.value)},
            }
        ]
    return []


def _review_reason(rule: QualityIntent) -> str:
    if rule.rule == "required_columns":
        return "Dataplex DataQualityRule does not directly prove ContractForge required-column schema presence parity."
    if rule.rule == "unique_key" and len(rule.columns) > 1:
        return "Composite unique_key remains on the validated BigQuery SQL quality path until native Dataplex readback is certified."
    return "No conservative Dataplex DataQualityRule mapping is available for this ContractForge rule."


def _dataplex_location(env: GCPEnvironment) -> str:
    location = (env.location or "us").strip()
    return location.lower()


def _bigquery_resource(project: str, dataset: str, table: str) -> str:
    return f"//bigquery.googleapis.com/projects/{project}/datasets/{dataset}/tables/{table}"


def _results_table(project: str, dataset: str) -> str:
    return f"projects/{project}/datasets/{dataset}/tables/contractforge_dataplex_quality_results"


def _results_table_sql(resource: str) -> str:
    match = re.fullmatch(r"projects/([^/]+)/datasets/([^/]+)/tables/([^/]+)", resource)
    if not match:
        return resource.replace("`", "")
    return ".".join(match.groups())


def _data_scan_id(dataset: str, table: str) -> str:
    value = _slug(f"cf-{dataset}-{table}-dq")
    return value[:63].rstrip("-") or "cf-data-quality"


def _rule_name(value: str) -> str:
    return _slug(value)[:63].strip("-") or "contractforge-rule"


def _slug(value: str) -> str:
    lowered = value.lower().replace("_", "-")
    cleaned = re.sub(r"[^a-z0-9-]+", "-", lowered)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"cf-{cleaned}"
    return cleaned


def _rule_type(rule: dict[str, Any]) -> str:
    for key in (
        "rangeExpectation",
        "nonNullExpectation",
        "setExpectation",
        "regexExpectation",
        "uniquenessExpectation",
        "statisticRangeExpectation",
        "rowConditionExpectation",
        "tableConditionExpectation",
        "sqlAssertion",
    ):
        if key in rule:
            return key
    return "unknown"
