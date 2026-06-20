"""Composable AWS review artifact renderers."""

from __future__ import annotations

from dataclasses import dataclass

from contractforge_core.planner import ExecutionPlan
from contractforge_core.semantic import SemanticContract
from contractforge_aws.operations import render_operations_insert_sql, render_operations_json
from contractforge_aws.annotations.rendering import render_annotations_evidence_sql, render_annotations_plan
from contractforge_aws.performance import (
    render_performance_benchmark_query,
    render_performance_profile,
    should_render_performance_profile,
)
from contractforge_aws.rendering.cloudformation import render_glue_job_cloudformation
from contractforge_aws.rendering.deployment import render_glue_job_definition
from contractforge_aws.quality.dqdl import render_quality_dqdl
from contractforge_aws.rendering.glue_job import can_render_glue_job, render_glue_job
from contractforge_aws.rendering.glue_job_outline import render_glue_job_outline
from contractforge_aws.rendering.iam import render_glue_job_iam_policy
from contractforge_aws.rendering.library_runner import render_library_runner_script
from contractforge_aws.governance.lakeformation import render_lake_formation_artifact
from contractforge_aws.governance.evidence import render_lake_formation_evidence_sql
from contractforge_aws.rendering.terraform import render_glue_job_terraform
from contractforge_aws.rendering.write_mode_review import render_write_mode_review, should_render_write_mode_review
from contractforge_aws.sources import render_native_passthrough_plan


@dataclass(frozen=True)
class AwsArtifactContext:
    prefix: str
    evidence_database: str
    contract: SemanticContract
    plan: ExecutionPlan | None
    environment_parameters: dict[str, object] | None = None
    artifact_uri: str | None = None


def render_contract_review_artifacts(context: AwsArtifactContext) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for renderer in _RENDERERS:
        artifacts.update(renderer(context))
    return artifacts


def _iam(context: AwsArtifactContext) -> dict[str, str]:
    return {
        f"{context.prefix}.iam_policy.json": render_glue_job_iam_policy(
            context.contract,
            evidence_database_name=context.evidence_database,
            environment_parameters=context.environment_parameters,
            artifact_uri=context.artifact_uri,
        )
    }


def _write_mode_review(context: AwsArtifactContext) -> dict[str, str]:
    if not should_render_write_mode_review(context.contract):
        return {}
    return {f"{context.prefix}.write_mode_review.md": render_write_mode_review(context.contract)}


def _quality(context: AwsArtifactContext) -> dict[str, str]:
    dqdl = render_quality_dqdl(context.contract)
    return {f"{context.prefix}.quality.dqdl": dqdl} if dqdl else {}


def _performance(context: AwsArtifactContext) -> dict[str, str]:
    if not should_render_performance_profile(context.contract):
        return {}
    return {
        f"{context.prefix}.performance_profile.json": render_performance_profile(context.contract),
        f"{context.prefix}.performance.sql": render_performance_benchmark_query(
            context.contract,
            evidence_database_name=context.evidence_database,
        ),
    }


def _annotations(context: AwsArtifactContext) -> dict[str, str]:
    annotations = render_annotations_plan(context.contract)
    if not annotations:
        return {}
    return {
        f"{context.prefix}.annotations.json": annotations,
        f"{context.prefix}.annotations_evidence.sql": render_annotations_evidence_sql(
            context.contract,
            database=context.evidence_database,
        ),
    }


def _operations(context: AwsArtifactContext) -> dict[str, str]:
    if not (context.contract.operations and context.contract.operations.metadata):
        return {}
    return {
        f"{context.prefix}.operations.json": render_operations_json(context.contract),
        f"{context.prefix}.operations.sql": render_operations_insert_sql(
            context.contract,
            database=context.evidence_database,
        ),
    }


def _native_passthrough(context: AwsArtifactContext) -> dict[str, str]:
    source = context.contract.source.raw or {}
    if source.get("type") != "native_passthrough" or not (source.get("system") and source.get("object")):
        return {}
    return {f"{context.prefix}.native_passthrough.json": render_native_passthrough_plan(source)}


def _lake_formation(context: AwsArtifactContext) -> dict[str, str]:
    artifact = render_lake_formation_artifact(context.contract)
    if not artifact:
        return {}
    return {
        f"{context.prefix}.lakeformation.json": artifact,
        f"{context.prefix}.lakeformation_evidence.sql": render_lake_formation_evidence_sql(
            context.contract,
            database=context.evidence_database,
        ),
    }


def _glue_job(context: AwsArtifactContext) -> dict[str, str]:
    if context.plan is not None and can_render_glue_job(context.contract):
        return {
            "runtime/contractforge_aws_runner.py": render_library_runner_script(),
            f"{context.prefix}.glue_job.py": render_glue_job(
                context.contract,
                evidence_database_name=context.evidence_database,
                environment_parameters=context.environment_parameters,
            ),
            f"{context.prefix}.glue_job_definition.json": render_glue_job_definition(
                context.contract,
                environment_parameters=context.environment_parameters,
            ),
            f"{context.prefix}.cloudformation.json": render_glue_job_cloudformation(
                context.contract,
                evidence_database_name=context.evidence_database,
                environment_parameters=context.environment_parameters,
            ),
            f"{context.prefix}.terraform.tf": render_glue_job_terraform(
                context.contract,
                evidence_database_name=context.evidence_database,
                environment_parameters=context.environment_parameters,
            ),
        }
    return {f"{context.prefix}.glue_job.todo.md": _render_glue_job_outline(context)}


def _render_glue_job_outline(context: AwsArtifactContext) -> str:
    return render_glue_job_outline(context.contract, context.plan)


_RENDERERS = (
    _iam,
    _write_mode_review,
    _quality,
    _performance,
    _annotations,
    _operations,
    _native_passthrough,
    _lake_formation,
    _glue_job,
)
