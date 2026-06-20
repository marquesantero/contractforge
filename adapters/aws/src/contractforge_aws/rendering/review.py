"""Render AWS planning review artifacts."""

from __future__ import annotations

import json

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.planner import ExecutionPlan, PlanningResult
from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG, glue_iceberg_capabilities
from contractforge_aws.contract_extensions import aws_extensions
from contractforge_aws.cost import render_operational_cost_query
from contractforge_aws.evidence import (
    render_create_evidence_tables_sql,
    render_create_state_tables_sql,
    render_evidence_table_notes,
)
from contractforge_aws.environment import AWSEnvironment
from contractforge_aws.rendering.artifact_registry import AwsArtifactContext, render_contract_review_artifacts
from contractforge_aws.rendering.manifest import render_deployment_manifest
from contractforge_aws.rendering.names import glue_database_name
from contractforge_aws.sources import list_aws_source_support


def render_aws_review_artifacts(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    contract: SemanticContract | None = None,
    environment: AWSEnvironment | None = None,
) -> RenderedArtifacts:
    prefix = _artifact_prefix(contract, plan)
    artifacts = {
        f"{prefix}.review.md": _render_review_markdown(contract=contract, plan=plan, planning=planning),
        f"{prefix}.capabilities.json": json.dumps(_capabilities_payload(), indent=2, sort_keys=True),
    }
    evidence_database = _evidence_database(contract, environment)
    artifacts[f"{prefix}.evidence.sql"] = render_evidence_table_notes(database=evidence_database)
    artifacts[f"{prefix}.evidence_ddl.sql"] = render_create_evidence_tables_sql(database=evidence_database)
    artifacts[f"{prefix}.state_ddl.sql"] = render_create_state_tables_sql(database=evidence_database)
    artifacts[f"{prefix}.cost.sql"] = render_operational_cost_query(database=evidence_database)
    if contract is not None:
        context = AwsArtifactContext(
            prefix,
            evidence_database,
            contract,
            plan,
            environment_parameters=environment.parameters if environment else None,
            artifact_uri=environment.artifact_uri if environment else None,
        )
        artifacts.update(render_contract_review_artifacts(context))
    elif plan is not None:
        artifacts[f"{prefix}.glue_job.todo.md"] = "# AWS Glue Job Outline\n\nNo contract was provided for rendering.\n"
    artifacts[f"{prefix}.deployment_manifest.json"] = render_deployment_manifest(
        prefix=prefix,
        evidence_database=evidence_database,
        contract=contract,
        plan=plan,
        planning=planning,
        artifacts=artifacts,
    )
    return RenderedArtifacts(artifacts=artifacts)


def _artifact_prefix(contract: SemanticContract | None, plan: ExecutionPlan | None) -> str:
    if contract is None:
        return (plan.platform if plan else AWS_SUBTARGET_GLUE_ICEBERG).replace(".", "_")
    namespace = (contract.target.namespace or "default").replace(".", "_")
    return f"{namespace}_{contract.target.name}"


def _evidence_database(contract: SemanticContract | None, environment: AWSEnvironment | None) -> str:
    if environment and environment.evidence_database:
        return environment.evidence_database
    if contract is None:
        return "contractforge_ops"
    return f"{glue_database_name(contract)}_ops"


def _capabilities_payload() -> dict[str, object]:
    capabilities = glue_iceberg_capabilities()
    return {
        "platform": capabilities.platform,
        "supports_append": capabilities.supports_append,
        "supports_overwrite": capabilities.supports_overwrite,
        "supports_merge": capabilities.supports_merge,
        "supports_hash_diff": capabilities.supports_hash_diff,
        "supports_scd2": capabilities.supports_scd2,
        "supports_snapshot_soft_delete": capabilities.supports_snapshot_soft_delete,
        "supports_schema_evolution": capabilities.supports_schema_evolution,
        "supports_row_filters": capabilities.supports_row_filters,
        "supports_column_masks": capabilities.supports_column_masks,
        "supports_available_now_streaming": capabilities.supports_available_now_streaming,
        "supports_expression_quality": capabilities.supports_expression_quality,
        "supports_shape": capabilities.supports_shape,
        "supports_transform": capabilities.supports_transform,
        "evidence_stores": list(capabilities.evidence_stores),
        "review_required_semantics": list(capabilities.review_required_semantics),
        "source_support": list(list_aws_source_support()),
    }


def _render_review_markdown(
    *,
    contract: SemanticContract | None,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
) -> str:
    lines = [
        "# AWS Glue Iceberg Planning Review",
        "",
        "This artifact summarizes planning status, review boundaries and generated AWS-native artifacts.",
        "For supported write/source/preparation/quality combinations, the adapter renders a Glue Spark/Iceberg job script without calling AWS services.",
        "",
    ]
    if contract:
        lines.extend(
            [
                "## Contract",
                "",
                f"- Source: `{contract.source.kind}`",
                f"- Target: `{contract.target.namespace or 'default'}.{contract.target.name}`",
                f"- Write mode: `{contract.write.mode}`",
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
    if contract:
        extensions = aws_extensions(contract)
        if extensions:
            lines.extend(["## AWS Extensions", ""])
            lines.extend(f"- `{name}`: `{redact_value(extensions[name])}`" for name in sorted(extensions))
            lines.append("")
    if plan:
        lines.extend(["## Abstract Plan", "", "| Step | Intent |", "| --- | --- |"])
        lines.extend(f"| `{step.name}` | {step.intent} |" for step in plan.steps)
        lines.append("")
    lines.extend(
        [
            "## Expected AWS Mapping",
            "",
            "| Core Intent | AWS Target |",
            "| --- | --- |",
            "| Source read | AWS Glue Spark reader over S3/JDBC/HTTP/catalog source |",
            "| Write target | Apache Iceberg table registered in AWS Glue Catalog |",
            "| Evidence | Iceberg evidence tables backed by S3 |",
            "| Governance review | Lake Formation permissions, data filters, and masking design |",
            "",
        ]
    )
    return "\n".join(lines)
