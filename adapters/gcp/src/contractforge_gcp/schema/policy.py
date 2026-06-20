"""BigQuery schema policy planning artifacts."""

from __future__ import annotations

import json

from contractforge_core.schema import SchemaPolicyPlan
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import target_dataset, target_project, target_table_id


def plan_bigquery_schema_policy(contract: SemanticContract) -> SchemaPolicyPlan:
    """Return the conservative GCP BigQuery schema-policy plan."""

    policy = contract.write.schema_policy
    if policy == "strict":
        return SchemaPolicyPlan(
            policy=policy,
            writer_options={},
            preflight_required=True,
            reason="Strict schema requires comparing source and BigQuery target columns before the write.",
        )
    if policy == "additive_only":
        return SchemaPolicyPlan(
            policy=policy,
            writer_options={"schemaUpdateOptions": "ALLOW_FIELD_ADDITION when an explicit nullable schema is supplied"},
            preflight_required=True,
            reason=(
                "Additive-only schema can use BigQuery nullable field additions after preflight validation. "
                "Removals and incompatible type changes stay blocked."
            ),
            warnings=(
                "BigQuery load-job schemaUpdateOptions require an explicit schema; the adapter does not infer one.",
            ),
        )
    return SchemaPolicyPlan(
        policy=policy,
        writer_options={"schemaUpdateOptions": "ALLOW_FIELD_ADDITION for nullable additions when explicitly supplied"},
        preflight_required=True,
        reason=(
            "Permissive schema can plan nullable additions, but type changes and column drops "
            "stay review-required before execution."
        ),
        warnings=(
            "Permissive does not mean automatic BigQuery type changes or column drops.",
            "Type widening or mutation is recorded as schema-change evidence and blocked by the stable runtime path.",
        ),
    )


def render_bigquery_schema_policy_plan(contract: SemanticContract, env: GCPEnvironment) -> str:
    """Render a deterministic BigQuery schema-policy review artifact."""

    plan = plan_bigquery_schema_policy(contract)
    table_id = target_table_id(contract, env)
    dataset = target_dataset(contract, env)
    project_id = target_project(contract, env) or env.project_id
    payload = {
        "kind": "contractforge.gcp.bigquery_schema_policy_plan.v1",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "status": "PLANNED_REVIEW_REQUIRED",
        "target": {
            "project_id": project_id,
            "dataset": dataset,
            "table": contract.target.name,
            "table_id": table_id,
        },
        "policy": plan.as_dict(),
        "bigquery": {
            "preflight_queries": {
                "target_columns": _target_columns_query(project_id, dataset, contract.target.name),
                "job_history": _job_history_query(project_id, env.location, table_id),
            },
            "apply_hints": _apply_hints(contract),
        },
        "evidence": {
            "schema_evidence_table": "contractforge_schema_evidence",
            "runtime_evidence_status": "PLANNED_NOT_EXECUTED",
        },
        "review_boundaries": [
            "This artifact does not compare live source and target schemas.",
            "Do not apply column removals or incompatible type changes automatically.",
            "BigQuery ALLOW_FIELD_ADDITION applies only when an explicit schema is provided and new fields are nullable.",
            "Automatic BigQuery type widening or mutation remains review-required outside the stable runtime path.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _apply_hints(contract: SemanticContract) -> list[dict[str, str]]:
    policy = contract.write.schema_policy
    if policy == "strict":
        return [
            {
                "name": "strict_preflight",
                "status": "REVIEW_REQUIRED",
                "hint": "Abort before write if source and target schemas differ after ignoring ContractForge control columns.",
            }
        ]
    hints = [
        {
            "name": "nullable_field_addition",
            "status": "PLANNED_REVIEW_REQUIRED",
            "hint": "For load jobs, use schemaUpdateOptions=['ALLOW_FIELD_ADDITION'] only with an explicit schema.",
        },
        {
            "name": "alter_table_add_column",
            "status": "PLANNED_REVIEW_REQUIRED",
            "hint": "For SQL/table writes, apply reviewed nullable additions with ALTER TABLE target ADD COLUMN column TYPE.",
        },
    ]
    if policy == "permissive":
        hints.append(
            {
                "name": "type_widening",
                "status": "REVIEW_REQUIRED",
                "hint": "Type widening or mutation is recorded as schema-change evidence and blocked unless a future reviewed DDL path is certified.",
            }
        )
    return hints


def _target_columns_query(project_id: str | None, dataset: str, table: str) -> str:
    prefix = f"`{project_id}.{dataset}.INFORMATION_SCHEMA.COLUMNS`" if project_id else f"`{dataset}.INFORMATION_SCHEMA.COLUMNS`"
    return (
        "SELECT column_name, data_type, is_nullable, ordinal_position "
        f"FROM {prefix} WHERE table_name = '{table}' ORDER BY ordinal_position"
    )


def _job_history_query(project_id: str | None, location: str | None, table_id: str) -> str:
    region = _jobs_region(location)
    prefix = f"`{project_id}.{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`" if project_id else f"`{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`"
    return (
        "SELECT job_id, creation_time, statement_type, error_result "
        f"FROM {prefix} WHERE destination_table.project_id IS NOT NULL "
        f"AND CONCAT(destination_table.project_id, '.', destination_table.dataset_id, '.', destination_table.table_id) = '{table_id}' "
        "ORDER BY creation_time DESC LIMIT 20"
    )


def _jobs_region(location: str | None) -> str:
    value = str(location or "US").strip().lower()
    if value in {"us", "eu"}:
        return f"region-{value}"
    return f"region-{value}"
