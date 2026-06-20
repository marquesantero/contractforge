"""Google Cloud adapter package for ContractForge."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("contractforge-gcp")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

from contractforge_gcp.adapter import GCPAdapter
from contractforge_gcp.api import plan_gcp_contract, render_gcp_contract
from contractforge_gcp.capabilities import GCP_SUBTARGET_BIGQUERY, gcp_bigquery_capabilities
from contractforge_gcp.cost import CostModel, build_operational_cost_report, render_operational_cost_query
from contractforge_gcp.dataplex import (
    has_dataplex_aspect_plan,
    has_dataplex_lineage_plan,
    has_dataplex_quality_plan,
    render_dataplex_aspect_plan,
    render_dataplex_data_quality_execution_plan,
    render_dataplex_data_quality_plan,
    render_dataplex_lineage_plan,
    run_dataplex_data_quality,
    run_dataplex_lineage_aspects,
)
from contractforge_gcp.deployment import (
    GCPProjectDeployment,
    deploy_gcp_project,
    project_deployment_json,
    render_gcp_deployment_manifest,
    render_gcp_project_deployment_manifest,
    render_gcp_workflows_cleanup_plan,
    render_gcp_workflows_evidence_readback_plan,
    render_gcp_workflows_execution_plan,
    render_gcp_workflows_runner_manifest,
    render_gcp_workflows_runner_yaml,
    run_gcp_workflows_orchestration,
    workflow_name,
)
from contractforge_gcp.evidence import render_deployment_ledger_insert_sql
from contractforge_gcp.governance import (
    annotation_steps,
    annotations_plan,
    governance_ledger_plan,
    governance_reconciliation_plan,
    has_annotations,
    has_governance_ledger_plan,
    has_governance_reconciliation_plan,
    render_bigquery_annotations_evidence_sql,
    render_bigquery_annotations_plan,
    render_bigquery_annotations_sql,
    render_bigquery_governance_evidence_insert_sql,
    render_bigquery_governance_ledger_plan,
    render_bigquery_governance_reconciliation_plan,
    run_bigquery_governance_reconciliation,
)
from contractforge_gcp.governance.policy_tags import (
    has_policy_tag_access,
    policy_tag_steps,
    policy_tags_plan,
    render_bigquery_policy_tags_plan,
)
from contractforge_gcp.lineage import (
    build_openlineage_event,
    openlineage_namespace,
    render_openlineage_insert_sql,
)
from contractforge_gcp.schema import (
    BigQuerySchemaPolicyResult,
    enforce_bigquery_schema_policy,
    plan_bigquery_schema_policy,
    render_bigquery_schema_policy_plan,
    schema_policy_job_evidence,
)
from contractforge_gcp.security import (
    has_secret_placeholders,
    render_gcp_source_secret_resolution_plan,
    resolve_gcp_secret_placeholders,
    secret_placeholder_refs,
)
from contractforge_gcp.source_review import (
    gcp_source_review_payload,
    render_gcp_source_review_json,
    render_gcp_source_review_markdown,
)
from contractforge_gcp.source_promotion import render_gcp_source_promotion_plan, run_gcp_source_promotion
from contractforge_gcp.smoke import (
    GCPContractSmokeResult,
    GCPProjectSmokeResult,
    project_smoke_result_json,
    run_gcp_contract_smoke,
    run_gcp_project_smoke,
)
from contractforge_gcp.sources import (
    classify_gcp_source,
    gcp_source_support,
    is_gcp_source_renderable,
    list_gcp_source_support,
    review_required_gcp_source_types,
)
from contractforge_gcp.write_modes import render_bigquery_advanced_write_mode_review, render_bigquery_advanced_write_sql

__all__ = [
    "GCPAdapter",
    "CostModel",
    "GCPProjectDeployment",
    "BigQuerySchemaPolicyResult",
    "GCPContractSmokeResult",
    "GCPProjectSmokeResult",
    "GCP_SUBTARGET_BIGQUERY",
    "__version__",
    "annotation_steps",
    "annotations_plan",
    "build_openlineage_event",
    "build_operational_cost_report",
    "classify_gcp_source",
    "gcp_bigquery_capabilities",
    "gcp_source_review_payload",
    "gcp_source_support",
    "governance_ledger_plan",
    "governance_reconciliation_plan",
    "has_annotations",
    "has_dataplex_aspect_plan",
    "has_dataplex_lineage_plan",
    "has_dataplex_quality_plan",
    "has_governance_ledger_plan",
    "has_governance_reconciliation_plan",
    "has_policy_tag_access",
    "has_secret_placeholders",
    "is_gcp_source_renderable",
    "list_gcp_source_support",
    "openlineage_namespace",
    "policy_tag_steps",
    "policy_tags_plan",
    "plan_bigquery_schema_policy",
    "plan_gcp_contract",
    "deploy_gcp_project",
    "enforce_bigquery_schema_policy",
    "project_deployment_json",
    "project_smoke_result_json",
    "render_bigquery_annotations_evidence_sql",
    "render_bigquery_annotations_plan",
    "render_bigquery_annotations_sql",
    "render_bigquery_governance_evidence_insert_sql",
    "render_bigquery_advanced_write_mode_review",
    "render_bigquery_advanced_write_sql",
    "render_bigquery_governance_ledger_plan",
    "render_bigquery_governance_reconciliation_plan",
    "render_bigquery_policy_tags_plan",
    "render_bigquery_schema_policy_plan",
    "render_deployment_ledger_insert_sql",
    "render_dataplex_aspect_plan",
    "render_dataplex_data_quality_execution_plan",
    "render_dataplex_data_quality_plan",
    "render_dataplex_lineage_plan",
    "run_dataplex_data_quality",
    "run_dataplex_lineage_aspects",
    "run_bigquery_governance_reconciliation",
    "run_gcp_source_promotion",
    "render_gcp_deployment_manifest",
    "render_gcp_project_deployment_manifest",
    "render_gcp_workflows_cleanup_plan",
    "render_gcp_workflows_evidence_readback_plan",
    "render_gcp_workflows_execution_plan",
    "render_gcp_source_review_json",
    "render_gcp_source_review_markdown",
    "render_gcp_source_promotion_plan",
    "render_gcp_source_secret_resolution_plan",
    "resolve_gcp_secret_placeholders",
    "render_gcp_workflows_runner_manifest",
    "render_gcp_workflows_runner_yaml",
    "render_gcp_contract",
    "render_operational_cost_query",
    "render_openlineage_insert_sql",
    "review_required_gcp_source_types",
    "run_gcp_workflows_orchestration",
    "run_gcp_contract_smoke",
    "run_gcp_project_smoke",
    "schema_policy_job_evidence",
    "secret_placeholder_refs",
    "workflow_name",
]
