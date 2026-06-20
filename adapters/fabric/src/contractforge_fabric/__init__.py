"""Microsoft Fabric adapter for ContractForge."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from contractforge_fabric.access import (
    FabricAccessApplyResult,
    access_plan,
    access_steps,
    apply_native_access_governance,
    has_access_intent,
    native_access_apply_steps,
    render_access_evidence_sql,
    render_access_plan,
)
from contractforge_fabric.annotations import (
    annotation_steps,
    annotations_plan,
    has_annotations,
    render_annotations_evidence_sql,
    render_annotations_plan,
)
from contractforge_fabric.adapter import FabricAdapter
from contractforge_fabric.api import plan_fabric_contract, render_fabric_contract
from contractforge_fabric.capabilities import FABRIC_SUBTARGET_LAKEHOUSE, fabric_lakehouse_capabilities
from contractforge_fabric.deployment import (
    FabricProjectDeployment,
    FabricProjectDeploymentStep,
    deploy_fabric_project,
    render_fabric_project_deployment_manifest,
    render_deployment_ledger_ddl_sql,
    render_deployment_ledger_insert_sql,
)
from contractforge_fabric.evidence import (
    evidence_table_names,
    render_create_evidence_tables_sql,
    render_evidence_table_notes,
    render_notebook_evidence_setup,
)
from contractforge_fabric.lineage import build_openlineage_event, render_openlineage_event_json
from contractforge_fabric.naming import openlineage_namespace, source_display_name, target_table_name
from contractforge_fabric.operations import (
    has_operations_metadata,
    operations_payload,
    render_operations_insert_sql,
    render_operations_json,
)
from contractforge_fabric.preparation import (
    can_render_preparation,
    can_render_shape,
    can_render_transform,
    render_flatten_helper,
    render_preparation,
    render_shape_preparation,
    render_transform_preparation,
    shape_requires_flatten,
)
from contractforge_fabric.quality import (
    can_render_quality_runtime,
    has_quality_rules,
    render_quality_gate_statement,
)
from contractforge_fabric.runtime import (
    FABRIC_RESOURCE,
    AzureCliFabricTokenProvider,
    FabricHttpRequest,
    FabricHttpResponse,
    FabricJobReference,
    FabricNotebookDeployment,
    FabricNotebookRunOutcome,
    FabricOperation,
    FabricPreflightCheck,
    FabricRestClient,
    FabricRestError,
    FabricWorkspacePreflight,
    check_fabric_workspace_preflight,
    classify_fabric_notebook_run_result,
    deploy_fabric_notebook_contract,
    fabric_notebook_default_lakehouse_execution_data,
    fabric_job_reference_from_url,
    fabric_rest_client_from_environment,
    run_fabric_notebook_from_environment,
)
from contractforge_fabric.smoke import (
    FabricContractSmokeResult,
    FabricProjectSmokeResult,
    FabricProjectSmokeStepResult,
    run_fabric_contract_smoke,
    run_fabric_project_smoke,
)
from contractforge_fabric.stabilization import fabric_stabilization_report
from contractforge_fabric.sources import fabric_source_support, list_fabric_source_support
from contractforge_fabric.sources import (
    fabric_source_review_payload,
    render_fabric_source_review_json,
    render_fabric_source_review_markdown,
)
from contractforge_fabric.state import (
    notebook_state_lock_options,
    notebook_state_watermark_column,
    render_create_state_tables_sql,
    state_table_names,
)
from contractforge_fabric.subtargets import adapter_for_subtarget, list_fabric_subtargets

try:
    __version__ = version("contractforge-fabric")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = [
    "FABRIC_SUBTARGET_LAKEHOUSE",
    "FABRIC_RESOURCE",
    "AzureCliFabricTokenProvider",
    "FabricAdapter",
    "FabricAccessApplyResult",
    "FabricHttpRequest",
    "FabricHttpResponse",
    "FabricJobReference",
    "FabricContractSmokeResult",
    "FabricProjectDeployment",
    "FabricProjectDeploymentStep",
    "FabricProjectSmokeResult",
    "FabricProjectSmokeStepResult",
    "FabricNotebookDeployment",
    "FabricNotebookRunOutcome",
    "FabricOperation",
    "FabricPreflightCheck",
    "FabricRestClient",
    "FabricRestError",
    "FabricWorkspacePreflight",
    "access_plan",
    "access_steps",
    "apply_native_access_governance",
    "annotation_steps",
    "annotations_plan",
    "fabric_rest_client_from_environment",
    "fabric_notebook_default_lakehouse_execution_data",
    "fabric_job_reference_from_url",
    "check_fabric_workspace_preflight",
    "classify_fabric_notebook_run_result",
    "deploy_fabric_notebook_contract",
    "deploy_fabric_project",
    "run_fabric_notebook_from_environment",
    "run_fabric_contract_smoke",
    "run_fabric_project_smoke",
    "adapter_for_subtarget",
    "can_render_quality_runtime",
    "build_openlineage_event",
    "can_render_preparation",
    "can_render_shape",
    "evidence_table_names",
    "fabric_lakehouse_capabilities",
    "fabric_stabilization_report",
    "fabric_source_support",
    "fabric_source_review_payload",
    "can_render_transform",
    "has_access_intent",
    "has_annotations",
    "has_operations_metadata",
    "has_quality_rules",
    "list_fabric_source_support",
    "list_fabric_subtargets",
    "notebook_state_lock_options",
    "native_access_apply_steps",
    "notebook_state_watermark_column",
    "openlineage_namespace",
    "operations_payload",
    "plan_fabric_contract",
    "render_annotations_evidence_sql",
    "render_annotations_plan",
    "render_access_evidence_sql",
    "render_access_plan",
    "render_create_evidence_tables_sql",
    "render_create_state_tables_sql",
    "render_evidence_table_notes",
    "render_fabric_contract",
    "render_fabric_project_deployment_manifest",
    "render_deployment_ledger_ddl_sql",
    "render_deployment_ledger_insert_sql",
    "render_fabric_source_review_json",
    "render_fabric_source_review_markdown",
    "render_notebook_evidence_setup",
    "render_openlineage_event_json",
    "render_flatten_helper",
    "render_operations_insert_sql",
    "render_operations_json",
    "render_preparation",
    "render_shape_preparation",
    "render_transform_preparation",
    "render_quality_gate_statement",
    "shape_requires_flatten",
    "source_display_name",
    "state_table_names",
    "target_table_name",
]
