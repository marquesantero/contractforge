"""Render BigQuery-oriented GCP adapter artifacts."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.planner import ExecutionPlan, PlanningResult
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.capabilities import GCP_SUBTARGET_BIGQUERY, gcp_bigquery_capabilities
from contractforge_gcp.dataplex import (
    render_dataplex_aspect_plan,
    render_dataplex_data_quality_execution_plan,
    render_dataplex_data_quality_plan,
    render_dataplex_lineage_plan,
)
from contractforge_gcp.deployment.manifest import render_gcp_deployment_manifest
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.governance.annotations import (
    render_bigquery_annotations_evidence_sql,
    render_bigquery_annotations_plan,
    render_bigquery_annotations_sql,
)
from contractforge_gcp.governance.ledger import render_bigquery_governance_ledger_plan
from contractforge_gcp.governance.reconciliation import render_bigquery_governance_reconciliation_plan
from contractforge_gcp.governance.policy_tags import render_bigquery_policy_tags_plan
from contractforge_gcp.rendering.evidence import render_bigquery_evidence_ddl
from contractforge_gcp.rendering.names import artifact_prefix, evidence_dataset, public_mode, target_table
from contractforge_gcp.rendering.sql import (
    render_bigquery_load_job_config,
    render_bigquery_quality_sql,
    render_bigquery_source_materialization_plan,
    render_bigquery_write_sql,
)
from contractforge_gcp.schema import render_bigquery_schema_policy_plan
from contractforge_gcp.security import render_gcp_source_secret_resolution_plan
from contractforge_gcp.source_promotion import render_gcp_source_promotion_plan
from contractforge_gcp.source_review import render_gcp_source_review_json, render_gcp_source_review_markdown
from contractforge_gcp.sources import list_gcp_source_support
from contractforge_gcp.write_modes import render_bigquery_advanced_write_mode_review


def render_gcp_bigquery_artifacts(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    contract: SemanticContract | None = None,
    raw_contract: dict[str, Any] | None = None,
    environment: GCPEnvironment | None = None,
) -> RenderedArtifacts:
    env = environment or GCPEnvironment()
    prefix = artifact_prefix(contract, plan)
    artifacts = {
        f"{prefix}.gcp.review.md": _planning_markdown(plan=plan, planning=planning, contract=contract, environment=env),
        f"{prefix}.gcp.capabilities.json": _capabilities_json(plan=plan, planning=planning, environment=env),
        f"{prefix}.gcp.source_support.json": json.dumps(list(list_gcp_source_support()), indent=2, sort_keys=True),
        f"{prefix}.gcp.evidence_ddl.sql": render_bigquery_evidence_ddl(
            project_id=env.project_id,
            dataset=evidence_dataset(contract, env),
        ),
    }
    if raw_contract is not None:
        artifacts[f"{prefix}.gcp.contract.json"] = json.dumps(raw_contract, indent=2, sort_keys=True)
    if contract is not None:
        artifacts[f"{prefix}.gcp.source_review.json"] = render_gcp_source_review_json(contract.source.raw)
        artifacts[f"{prefix}.gcp.source_review.md"] = render_gcp_source_review_markdown(contract.source.raw)
        source_promotion = render_gcp_source_promotion_plan(contract.source.raw, environment=env)
        if source_promotion:
            artifacts[f"{prefix}.gcp.source_promotion_plan.json"] = source_promotion
        artifacts[f"{prefix}.gcp.schema_policy.json"] = render_bigquery_schema_policy_plan(contract, env)
        artifacts[f"{prefix}.gcp.write.sql"] = render_bigquery_write_sql(contract, env)
        load_config = render_bigquery_load_job_config(contract, env)
        if load_config:
            artifacts[f"{prefix}.gcp.load_job.json"] = load_config
        source_materialization = render_bigquery_source_materialization_plan(contract, env)
        if source_materialization:
            artifacts[f"{prefix}.gcp.source_materialization.json"] = source_materialization
        secret_resolution = render_gcp_source_secret_resolution_plan(contract, env)
        if secret_resolution:
            artifacts[f"{prefix}.gcp.source_secret_resolution.json"] = secret_resolution
        quality_sql = render_bigquery_quality_sql(contract, env)
        if quality_sql:
            artifacts[f"{prefix}.gcp.quality.sql"] = quality_sql
        advanced_write_review = render_bigquery_advanced_write_mode_review(contract, env)
        if advanced_write_review:
            artifacts[f"{prefix}.gcp.advanced_write_mode_review.json"] = advanced_write_review
        dataplex_quality_plan = render_dataplex_data_quality_plan(contract, env)
        if dataplex_quality_plan:
            artifacts[f"{prefix}.gcp.dataplex_data_quality.json"] = dataplex_quality_plan
        dataplex_execution_plan = render_dataplex_data_quality_execution_plan(contract, env)
        if dataplex_execution_plan:
            artifacts[f"{prefix}.gcp.dataplex_data_quality_execution.json"] = dataplex_execution_plan
        dataplex_lineage_plan = render_dataplex_lineage_plan(contract, env)
        if dataplex_lineage_plan:
            artifacts[f"{prefix}.gcp.dataplex_lineage.json"] = dataplex_lineage_plan
        dataplex_aspect_plan = render_dataplex_aspect_plan(contract, env)
        if dataplex_aspect_plan:
            artifacts[f"{prefix}.gcp.dataplex_aspects.json"] = dataplex_aspect_plan
        annotations_sql = render_bigquery_annotations_sql(contract, env)
        annotations_plan = render_bigquery_annotations_plan(contract, env)
        if annotations_plan:
            artifacts[f"{prefix}.gcp.annotations.sql"] = annotations_sql
            artifacts[f"{prefix}.gcp.annotations.json"] = annotations_plan
            artifacts[f"{prefix}.gcp.annotations_evidence.sql"] = render_bigquery_annotations_evidence_sql(contract, env)
        policy_tags_plan = render_bigquery_policy_tags_plan(contract, env)
        if policy_tags_plan:
            artifacts[f"{prefix}.gcp.policy_tags.json"] = policy_tags_plan
        governance_ledger_plan = render_bigquery_governance_ledger_plan(contract, env)
        if governance_ledger_plan:
            artifacts[f"{prefix}.gcp.governance_ledger.json"] = governance_ledger_plan
            artifacts[f"{prefix}.gcp.governance_reconciliation.json"] = render_bigquery_governance_reconciliation_plan(
                contract,
                env,
            )
        artifacts[f"{prefix}.gcp.deployment_manifest.json"] = render_gcp_deployment_manifest(
            contract=contract,
            environment=env,
            planning=planning,
            artifacts=artifacts,
        )
    manifest_name = f"{prefix}.gcp.manifest.json"
    artifacts[manifest_name] = _manifest_json(plan=plan, planning=planning, artifacts=artifacts, manifest_name=manifest_name)
    return RenderedArtifacts(artifacts=artifacts)


def _planning_markdown(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    contract: SemanticContract | None,
    environment: GCPEnvironment,
) -> str:
    lines = [
        "# GCP BigQuery Planning Review",
        "",
        "This artifact summarizes how a ContractForge contract maps to Google Cloud BigQuery.",
        "The current adapter renders BigQuery SQL, load-job configuration, schema-policy planning and evidence DDL for the documented stable BigQuery surface.",
        "",
        "## GCP Binding",
        "",
        f"- Project: `{environment.project_id or 'UNSPECIFIED'}`",
        f"- Location: `{environment.location or 'UNSPECIFIED'}`",
        f"- Dataset: `{environment.dataset or 'contractforge'}`",
        f"- Evidence dataset: `{environment.evidence_dataset or environment.dataset or 'contractforge_ops'}`",
        f"- Staging bucket: `{environment.staging_bucket or 'UNSPECIFIED'}`",
        "",
    ]
    if contract:
        lines.extend(
            [
                "## Contract",
                "",
                f"- Source: `{contract.source.kind}`",
                f"- Target: `{target_table(contract, environment)}`",
                f"- Write mode: `{public_mode(contract.write.mode)}`",
                "",
            ]
        )
    if planning:
        lines.extend(["## Planning Result", "", f"- Status: `{planning.status}`", ""])
        if planning.blockers:
            lines.extend(["### Blockers", ""])
            lines.extend(f"- `{blocker.code}`: {blocker.message}" for blocker in planning.blockers)
            lines.append("")
        if planning.warnings:
            lines.extend(["### Warnings", ""])
            lines.extend(f"- `{warning.code}`: {warning.message}" for warning in planning.warnings)
            lines.append("")
    if plan:
        lines.extend(["## Abstract Plan", "", "| Step | Intent |", "| --- | --- |"])
        lines.extend(f"| `{step.name}` | {step.intent} |" for step in plan.steps)
        lines.append("")
    return "\n".join(lines)


def _capabilities_json(*, plan: ExecutionPlan | None, planning: PlanningResult | None, environment: GCPEnvironment) -> str:
    capabilities = gcp_bigquery_capabilities()
    payload = {
        "adapter": "gcp",
        "subtarget": plan.platform if plan else GCP_SUBTARGET_BIGQUERY,
        "planning_status": planning.status if planning else None,
        "supports": {
            "append": capabilities.supports_append,
            "overwrite": capabilities.supports_overwrite,
            "upsert": capabilities.supports_merge,
            "hash_diff_upsert": capabilities.supports_hash_diff,
            "historical": capabilities.supports_scd2,
            "snapshot_reconcile_soft_delete": capabilities.supports_snapshot_soft_delete,
            "schema_evolution": capabilities.supports_schema_evolution,
            "row_filters": capabilities.supports_row_filters,
            "column_masks": capabilities.supports_column_masks,
            "available_now_streaming": capabilities.supports_available_now_streaming,
            "expression_quality": capabilities.supports_expression_quality,
        },
        "evidence": {"stores": list(capabilities.evidence_stores), "dataset": environment.evidence_dataset},
        "runtime": {
            "status": "single_contract_smoke_available",
            "project_id": environment.project_id,
            "location": environment.location,
            "dataset": environment.dataset,
            "staging_bucket": environment.staging_bucket,
            "service_account": environment.service_account,
        },
        "review_required_semantics": [public_mode(item) for item in capabilities.review_required_semantics],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _manifest_json(
    *, plan: ExecutionPlan | None, planning: PlanningResult | None, artifacts: dict[str, str], manifest_name: str
) -> str:
    payload = {
        "adapter": "gcp",
        "subtarget": plan.platform if plan else GCP_SUBTARGET_BIGQUERY,
        "planning_status": planning.status if planning else None,
        "artifact_summary": {
            "mode": "bigquery_render_bundle",
            "execution_model": "single_contract_bigquery_smoke",
            "deployable": True,
            "orchestration_included": False,
            "count": len(artifacts) + 1,
            "bytes": sum(len(body.encode("utf-8")) for body in artifacts.values()),
        },
        "artifacts": sorted(tuple(artifacts) + (manifest_name,)),
    }
    return json.dumps(payload, indent=2, sort_keys=True)
