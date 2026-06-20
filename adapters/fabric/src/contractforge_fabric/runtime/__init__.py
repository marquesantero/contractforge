"""Fabric runtime primitives."""

from contractforge_fabric.runtime.auth import FABRIC_RESOURCE, AzureCliFabricTokenProvider
from contractforge_fabric.runtime.factory import fabric_rest_client_from_environment
from contractforge_fabric.runtime.notebook import (
    FabricNotebookDeployment,
    FabricNotebookRunOutcome,
    classify_fabric_notebook_run_result,
    definition_fingerprint,
    deploy_fabric_notebook_contract,
    fabric_notebook_default_lakehouse_execution_data,
    run_fabric_notebook_from_environment,
)
from contractforge_fabric.runtime.preflight import (
    FabricPreflightCheck,
    FabricWorkspacePreflight,
    check_fabric_workspace_preflight,
)
from contractforge_fabric.runtime.rest import (
    FabricHttpRequest,
    FabricHttpResponse,
    FabricJobReference,
    FabricOperation,
    FabricRestClient,
    FabricRestError,
    fabric_job_reference_from_url,
)
from contractforge_fabric.smoke import (
    FabricContractSmokeResult,
    FabricProjectSmokeResult,
    FabricProjectSmokeStepResult,
    run_fabric_contract_smoke,
    run_fabric_project_smoke,
)

__all__ = [
    "FABRIC_RESOURCE",
    "AzureCliFabricTokenProvider",
    "FabricNotebookDeployment",
    "FabricNotebookRunOutcome",
    "FabricPreflightCheck",
    "FabricWorkspacePreflight",
    "FabricContractSmokeResult",
    "FabricProjectSmokeResult",
    "FabricProjectSmokeStepResult",
    "fabric_rest_client_from_environment",
    "fabric_notebook_default_lakehouse_execution_data",
    "classify_fabric_notebook_run_result",
    "definition_fingerprint",
    "deploy_fabric_notebook_contract",
    "run_fabric_notebook_from_environment",
    "check_fabric_workspace_preflight",
    "FabricHttpRequest",
    "FabricHttpResponse",
    "FabricJobReference",
    "FabricOperation",
    "FabricRestClient",
    "FabricRestError",
    "fabric_job_reference_from_url",
    "run_fabric_contract_smoke",
    "run_fabric_project_smoke",
]
