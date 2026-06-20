"""Fabric contract smoke workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.runtime.factory import fabric_rest_client_from_environment
from contractforge_fabric.runtime.notebook import (
    FabricNotebookDeployment,
    FabricNotebookRunOutcome,
    classify_fabric_notebook_run_result,
    deploy_fabric_notebook_contract,
    fabric_notebook_default_lakehouse_execution_data,
)
from contractforge_fabric.runtime.preflight import FabricWorkspacePreflight, check_fabric_workspace_preflight
from contractforge_fabric.runtime.rest import FabricJobReference, FabricOperation, FabricRestClient, fabric_job_reference_from_url


@dataclass(frozen=True)
class FabricContractSmokeResult:
    status: str
    preflight: FabricWorkspacePreflight
    deployment: FabricNotebookDeployment | None
    run_operation: FabricOperation | None
    job_reference: FabricJobReference | None
    outcome: FabricNotebookRunOutcome | None

    @property
    def ok(self) -> bool:
        return self.status == "SUCCEEDED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ok": self.ok,
            "preflight": {
                "status": self.preflight.status,
                "workspace": self.preflight.workspace,
                "items": self.preflight.items,
                "checks": [asdict(check) for check in self.preflight.checks],
            },
            "deployment": None if self.deployment is None else asdict(self.deployment),
            "run_operation": None if self.run_operation is None else asdict(self.run_operation),
            "job_reference": None if self.job_reference is None else asdict(self.job_reference),
            "outcome": None if self.outcome is None else asdict(self.outcome),
        }


def run_fabric_contract_smoke(
    contract: dict[str, Any],
    environment: FabricEnvironment | dict[str, Any],
    *,
    client: FabricRestClient | None = None,
    update_existing: bool = True,
    wait: bool = True,
    max_attempts: int = 30,
    retry_after_seconds: int | None = None,
) -> FabricContractSmokeResult:
    """Preflight, deploy and optionally run a Fabric Notebook generated from a contract."""

    env = environment if isinstance(environment, FabricEnvironment) else FabricEnvironment.from_contract(environment)
    client = client or fabric_rest_client_from_environment(env)
    preflight = check_fabric_workspace_preflight(
        env,
        client=client,
        require_lakehouse=True,
        require_notebook=False,
    )
    if not preflight.ok:
        return FabricContractSmokeResult(
            status="BLOCKED",
            preflight=preflight,
            deployment=None,
            run_operation=None,
            job_reference=None,
            outcome=None,
        )

    deployment = deploy_fabric_notebook_contract(
        contract,
        env,
        client=client,
        update_existing=update_existing,
    )
    if deployment.operation is not None:
        client.poll_operation(deployment.operation, max_attempts=max_attempts)
    if deployment.action == "update_blocked":
        return FabricContractSmokeResult(
            status="BLOCKED",
            preflight=preflight,
            deployment=deployment,
            run_operation=None,
            job_reference=None,
            outcome=None,
        )

    notebook_id = deployment.notebook_id or client.resolve_item_id(
        item_type="Notebook",
        display_name=deployment.display_name,
    )
    lakehouse_id = env.lakehouse_id or _resolved_item_id(preflight, "lakehouse")
    if not lakehouse_id:
        raise ValueError("Fabric smoke requires a resolved lakehouse_id")
    if not env.workspace_id:
        raise ValueError("Fabric smoke requires workspace_id")

    run_operation = client.run_notebook(
        notebook_id=notebook_id,
        execution_data=fabric_notebook_default_lakehouse_execution_data(
            workspace_id=env.workspace_id,
            lakehouse_id=lakehouse_id,
        ),
    )
    job_reference = fabric_job_reference_from_url(run_operation.location)
    if not wait:
        outcome = FabricNotebookRunOutcome(
            status="RUNNING",
            code="FABRIC_NOTEBOOK_RUN_SUBMITTED",
            message="Fabric notebook run was submitted.",
            raw={"job_instance_id": job_reference.job_instance_id},
        )
        return FabricContractSmokeResult(
            status=outcome.status,
            preflight=preflight,
            deployment=deployment,
            run_operation=run_operation,
            job_reference=job_reference,
            outcome=outcome,
        )

    result = client.wait_job_instance(
        item_id=job_reference.item_id,
        job_instance_id=job_reference.job_instance_id,
        max_attempts=max_attempts,
        retry_after_seconds=retry_after_seconds or run_operation.retry_after_seconds or 60,
    )
    outcome = classify_fabric_notebook_run_result(result)
    return FabricContractSmokeResult(
        status=outcome.status,
        preflight=preflight,
        deployment=deployment,
        run_operation=run_operation,
        job_reference=job_reference,
        outcome=outcome,
    )


def _resolved_item_id(preflight: FabricWorkspacePreflight, key: str) -> str | None:
    item = preflight.items.get(key)
    item_id = item.get("id") if item else None
    return item_id if isinstance(item_id, str) and item_id else None
