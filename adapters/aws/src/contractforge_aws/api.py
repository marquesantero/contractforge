"""High-level AWS adapter API."""

from __future__ import annotations

from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.planner import PlanningResult
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG
from contractforge_aws.cost import CostModel, render_operational_cost_query
from contractforge_aws.deployment_api import (
    render_aws_glue_job_cloudformation,
    render_aws_glue_job_definition,
    render_aws_glue_job_iam_policy,
    render_aws_glue_job_terraform,
)
from contractforge_aws.environment import AWSEnvironment
from contractforge_aws.operations import render_operations_insert_sql, render_operations_json
from contractforge_aws.rendering import (
    render_annotations_evidence_sql,
    render_annotations_plan,
    render_lake_formation_artifact,
    render_lake_formation_evidence_sql,
    render_quality_dqdl,
)
from contractforge_aws.rendering.names import glue_database_name
from contractforge_aws.sources import render_native_passthrough_plan
from contractforge_aws.subtargets import adapter_for_subtarget, validate_aws_subtarget


def plan_aws_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    environment: dict[str, Any] | None = None,
) -> PlanningResult:
    semantic = semantic_contract_from_mapping(contract)
    adapter = adapter_for_subtarget(subtarget, environment=environment)
    return adapter.plan(semantic)


def render_aws_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    environment: dict[str, Any] | None = None,
) -> RenderedArtifacts:
    semantic = semantic_contract_from_mapping(contract)
    adapter = adapter_for_subtarget(subtarget, environment=environment)
    return adapter.render_contract(semantic)


def render_aws_deployment_manifest(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    environment: dict[str, Any] | None = None,
) -> str:
    """Render the AWS deployment manifest for a contract."""

    rendered = render_aws_contract(contract, subtarget=subtarget, environment=environment).artifacts
    for name, body in rendered.items():
        if name.endswith(".deployment_manifest.json"):
            return body
    raise RuntimeError("AWS deployment manifest was not rendered")


def render_aws_quality_dqdl(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
) -> str:
    """Render an AWS Glue Data Quality DQDL ruleset from contract quality rules.

    Returns an empty string when no quality rule maps to a DQDL rule.
    """

    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    return render_quality_dqdl(semantic)


def render_aws_lake_formation_plan(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
) -> str:
    """Render Lake Formation grant/data-filter artifacts from the access section.

    Returns an empty string when the contract declares no access grants, row
    filters or column masks.
    """

    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    return render_lake_formation_artifact(semantic)


def render_aws_lake_formation_evidence_sql(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    database: str | None = None,
    environment: dict[str, Any] | None = None,
    run_id: str = "${run_id}",
) -> str:
    """Render governance evidence SQL for the Lake Formation artifact."""

    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    evidence_database = _evidence_database(semantic, database=database, environment=environment)
    return render_lake_formation_evidence_sql(semantic, database=evidence_database, run_id=run_id)


def render_aws_annotations_plan(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
) -> str:
    """Render an AWS Glue Catalog annotation update plan."""

    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    return render_annotations_plan(semantic)


def render_aws_annotations_evidence_sql(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    database: str | None = None,
    environment: dict[str, Any] | None = None,
    run_id: str = "${run_id}",
) -> str:
    """Render annotation evidence SQL for Glue Catalog metadata plans."""

    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    evidence_database = _evidence_database(semantic, database=database, environment=environment)
    return render_annotations_evidence_sql(semantic, database=evidence_database, run_id=run_id)


def render_aws_operations_json(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
) -> str:
    """Render normalized operations metadata JSON."""

    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    return render_operations_json(semantic)


def render_aws_operations_evidence_sql(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    database: str | None = None,
    environment: dict[str, Any] | None = None,
    run_id: str = "${run_id}",
) -> str:
    """Render operations metadata evidence SQL."""

    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    evidence_database = _evidence_database(semantic, database=database, environment=environment)
    return render_operations_insert_sql(semantic, database=evidence_database, run_id=run_id)


def render_aws_native_passthrough_plan(
    source: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
) -> str:
    """Render an AWS-native service handoff plan for ``source.type=native_passthrough``."""

    validate_aws_subtarget(subtarget)
    return render_native_passthrough_plan(source)


def render_aws_operational_cost_query(
    *,
    database: str | None = None,
    environment: dict[str, Any] | None = None,
    lookback_days: int = 30,
    group_by: tuple[str, ...] | None = None,
    cost_model: CostModel | None = None,
    include_failed: bool = True,
) -> str:
    """Render a query-only AWS operational cost report over evidence tables."""

    env = AWSEnvironment.from_contract(environment)
    return render_operational_cost_query(
        database=database or env.evidence_database or "contractforge_ops",
        lookback_days=lookback_days,
        group_by=group_by,
        cost_model=cost_model,
        include_failed=include_failed,
    )


def _evidence_database(
    semantic,
    *,
    database: str | None,
    environment: dict[str, Any] | None,
) -> str:
    env = AWSEnvironment.from_contract(environment)
    return database or env.evidence_database or f"{glue_database_name(semantic)}_ops"


_adapter_for_subtarget = adapter_for_subtarget
