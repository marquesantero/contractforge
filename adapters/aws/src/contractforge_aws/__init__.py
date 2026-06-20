"""Public API for the ContractForge AWS adapter."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from contractforge_aws.adapter import AWSAdapter
from contractforge_aws.api import (
    plan_aws_contract,
    render_aws_annotations_evidence_sql,
    render_aws_annotations_plan,
    render_aws_contract,
    render_aws_deployment_manifest,
    render_aws_glue_job_cloudformation,
    render_aws_glue_job_definition,
    render_aws_glue_job_iam_policy,
    render_aws_glue_job_terraform,
    render_aws_lake_formation_evidence_sql,
    render_aws_lake_formation_plan,
    render_aws_native_passthrough_plan,
    render_aws_operations_evidence_sql,
    render_aws_operations_json,
    render_aws_operational_cost_query,
    render_aws_quality_dqdl,
)
from contractforge_aws.runtime import (
    AthenaQueryResult,
    AthenaSqlRunner,
    audit_evidence_tables,
    apply_aws_annotations_contract,
    apply_aws_annotations_plan,
    apply_aws_lake_formation_contract,
    apply_aws_lake_formation_plan,
    create_or_update_schedule_payload,
    create_or_update_state_machine_payload,
    ensure_aws_evidence_tables,
    deploy_aws_contract_to_glue,
    get_aws_glue_job_run_status,
    get_state_machine_execution_status,
    publish_aws_contract_artifacts_to_s3,
    record_aws_operations_contract,
    reconcile_aws_glue_job_run_evidence,
    register_aws_glue_job,
    register_aws_glue_job_definition_payload,
    render_aws_glue_job_run_evidence_sql,
    start_aws_glue_job_run,
    start_state_machine_execution,
    wait_aws_glue_job_run,
    wait_state_machine_execution,
)
from contractforge_aws.orchestration import (
    render_eventbridge_scheduler_payload,
    render_stepfunctions_state_machine_definition,
    render_stepfunctions_state_machine_payload,
)
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG, glue_iceberg_capabilities
from contractforge_aws.cost import CostModel, render_operational_cost_query
from contractforge_aws.environment import AWSEnvironment
from contractforge_aws.evidence import render_deployment_ledger_insert_sql
from contractforge_aws.lineage import (
    build_openlineage_event,
    openlineage_namespace,
    render_openlineage_insert_sql,
)
from contractforge_aws.subtargets import list_aws_subtargets

try:
    __version__ = _version("contractforge-aws")
except PackageNotFoundError:  # pragma: no cover - editable/source tree without installed metadata
    __version__ = "0.2.0"

__all__ = [
    "AWSAdapter",
    "AWSEnvironment",
    "AWS_SUBTARGET_GLUE_ICEBERG",
    "AthenaQueryResult",
    "AthenaSqlRunner",
    "CostModel",
    "__version__",
    "apply_aws_annotations_contract",
    "apply_aws_annotations_plan",
    "audit_evidence_tables",
    "create_or_update_schedule_payload",
    "create_or_update_state_machine_payload",
    "ensure_aws_evidence_tables",
    "deploy_aws_contract_to_glue",
    "get_aws_glue_job_run_status",
    "get_state_machine_execution_status",
    "glue_iceberg_capabilities",
    "build_openlineage_event",
    "apply_aws_lake_formation_contract",
    "apply_aws_lake_formation_plan",
    "list_aws_subtargets",
    "openlineage_namespace",
    "plan_aws_contract",
    "publish_aws_contract_artifacts_to_s3",
    "record_aws_operations_contract",
    "reconcile_aws_glue_job_run_evidence",
    "register_aws_glue_job",
    "register_aws_glue_job_definition_payload",
    "render_aws_annotations_evidence_sql",
    "render_aws_annotations_plan",
    "render_aws_contract",
    "render_aws_deployment_manifest",
    "render_deployment_ledger_insert_sql",
    "render_aws_glue_job_cloudformation",
    "render_aws_glue_job_definition",
    "render_aws_glue_job_iam_policy",
    "render_aws_glue_job_terraform",
    "render_aws_glue_job_run_evidence_sql",
    "render_aws_lake_formation_evidence_sql",
    "render_aws_lake_formation_plan",
    "render_aws_native_passthrough_plan",
    "render_aws_operations_evidence_sql",
    "render_aws_operations_json",
    "render_aws_operational_cost_query",
    "render_aws_quality_dqdl",
    "render_operational_cost_query",
    "render_openlineage_insert_sql",
    "render_eventbridge_scheduler_payload",
    "render_stepfunctions_state_machine_definition",
    "render_stepfunctions_state_machine_payload",
    "start_aws_glue_job_run",
    "start_state_machine_execution",
    "wait_aws_glue_job_run",
    "wait_state_machine_execution",
]
