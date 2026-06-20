"""Read-only Fabric runtime preflight checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.runtime.factory import fabric_rest_client_from_environment
from contractforge_fabric.runtime.rest import FabricRestClient, FabricRestError


@dataclass(frozen=True)
class FabricPreflightCheck:
    code: str
    status: str
    message: str
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class FabricWorkspacePreflight:
    status: str
    workspace: dict[str, Any] | None
    items: dict[str, dict[str, Any] | None]
    checks: tuple[FabricPreflightCheck, ...]

    @property
    def ok(self) -> bool:
        return self.status in {"OK", "OK_WITH_WARNINGS"}


def check_fabric_workspace_preflight(
    environment: FabricEnvironment | dict[str, Any],
    *,
    client: FabricRestClient | None = None,
    require_capacity: bool = True,
    require_lakehouse: bool = False,
    require_notebook: bool = False,
    check_spark_settings: bool = False,
    check_notebook_jobs: bool = False,
) -> FabricWorkspacePreflight:
    """Resolve a Fabric workspace and verify read-only capacity readiness."""

    env = environment if isinstance(environment, FabricEnvironment) else FabricEnvironment.from_contract(environment)
    checks: list[FabricPreflightCheck] = []
    items: dict[str, dict[str, Any] | None] = {}
    workspace_id = env.workspace_id

    if client is None:
        client = fabric_rest_client_from_environment(env)

    if not workspace_id and env.workspace_name:
        try:
            workspace_id = client.resolve_workspace_id(env.workspace_name)
            checks.append(
                FabricPreflightCheck(
                    code="FABRIC_WORKSPACE_RESOLVED_BY_NAME",
                    status="OK",
                    message=f"Resolved Fabric workspace `{env.workspace_name}`.",
                    details={"workspace_id": workspace_id},
                )
            )
        except FabricRestError as exc:
            checks.append(
                FabricPreflightCheck(
                    code="FABRIC_WORKSPACE_RESOLUTION_FAILED",
                    status="BLOCKED",
                    message=str(exc),
                )
            )
            return FabricWorkspacePreflight(status="BLOCKED", workspace=None, items=items, checks=tuple(checks))

    if not workspace_id:
        checks.append(
            FabricPreflightCheck(
                code="FABRIC_WORKSPACE_REQUIRED",
                status="BLOCKED",
                message="Fabric workspace_id or unique workspace_name is required.",
            )
        )
        return FabricWorkspacePreflight(status="BLOCKED", workspace=None, items=items, checks=tuple(checks))

    try:
        workspace = client.get_workspace(workspace_id)
    except FabricRestError as exc:
        checks.append(
            FabricPreflightCheck(
                code="FABRIC_WORKSPACE_GET_FAILED",
                status="BLOCKED",
                message=str(exc),
                details={"workspace_id": workspace_id},
            )
        )
        return FabricWorkspacePreflight(status="BLOCKED", workspace=None, items=items, checks=tuple(checks))

    checks.append(
        FabricPreflightCheck(
            code="FABRIC_WORKSPACE_READABLE",
            status="OK",
            message="Fabric workspace metadata is readable.",
            details=_workspace_details(workspace),
        )
    )
    capacity_id = workspace.get("capacityId")
    assignment = workspace.get("capacityAssignmentProgress")
    if require_capacity and not capacity_id:
        checks.append(
            FabricPreflightCheck(
                code="FABRIC_WORKSPACE_CAPACITY_REQUIRED",
                status="BLOCKED",
                message="Fabric workspace is not assigned to a supported capacity.",
                details=_workspace_details(workspace),
            )
        )
    else:
        checks.append(
            FabricPreflightCheck(
                code="FABRIC_WORKSPACE_CAPACITY_ASSIGNED",
                status="OK",
                message="Fabric workspace has a capacity assignment.",
                details={"capacity_id": capacity_id, "capacity_assignment_progress": assignment},
            )
        )

    if check_spark_settings and capacity_id:
        checks.extend(_spark_settings_checks(client=client, capacity_id=str(capacity_id)))

    if env.lakehouse_id or env.lakehouse_name or require_lakehouse:
        lakehouse = _resolve_item(
            client=client,
            item_type="Lakehouse",
            item_id=env.lakehouse_id,
            item_name=env.lakehouse_name,
            required=require_lakehouse,
        )
        checks.append(lakehouse.check)
        items["lakehouse"] = lakehouse.item

    if env.notebook_id or env.notebook_name or require_notebook:
        notebook = _resolve_item(
            client=client,
            item_type="Notebook",
            item_id=env.notebook_id,
            item_name=env.notebook_name,
            required=require_notebook,
        )
        checks.append(notebook.check)
        items["notebook"] = notebook.item
        if check_notebook_jobs:
            checks.append(_notebook_jobs_check(client=client, notebook=notebook.item))
    elif check_notebook_jobs:
        checks.append(
            FabricPreflightCheck(
                code="FABRIC_NOTEBOOK_JOBS_SKIPPED",
                status="WARNING",
                message="Notebook job history was not checked because no notebook id or name was configured.",
            )
        )

    status = _preflight_status(checks)
    return FabricWorkspacePreflight(status=status, workspace=workspace, items=items, checks=tuple(checks))


@dataclass(frozen=True)
class _ItemResolution:
    item: dict[str, Any] | None
    check: FabricPreflightCheck


def _resolve_item(
    *,
    client: FabricRestClient,
    item_type: str,
    item_id: str | None,
    item_name: str | None,
    required: bool,
) -> _ItemResolution:
    try:
        candidates = client.list_items(item_type=item_type)
    except FabricRestError as exc:
        return _ItemResolution(
            item=None,
            check=FabricPreflightCheck(
                code=f"FABRIC_{item_type.upper()}_LIST_FAILED",
                status="BLOCKED" if required else "WARNING",
                message=str(exc),
            ),
        )

    if item_id:
        matches = [item for item in candidates if item.get("id") == item_id]
    elif item_name:
        matches = [
            item
            for item in candidates
            if str(item.get("displayName") or "").casefold() == item_name.casefold()
        ]
    else:
        matches = candidates

    if len(matches) == 1:
        return _ItemResolution(
            item=matches[0],
            check=FabricPreflightCheck(
                code=f"FABRIC_{item_type.upper()}_RESOLVED",
                status="OK",
                message=f"Fabric {item_type} item is readable.",
                details=_item_details(matches[0]),
            ),
        )
    if len(matches) > 1:
        return _ItemResolution(
            item=None,
            check=FabricPreflightCheck(
                code=f"FABRIC_{item_type.upper()}_NOT_UNIQUE",
                status="BLOCKED",
                message=f"Fabric {item_type} item is not unique; configure an explicit item id.",
                details={"matches": [_item_details(item) for item in matches]},
            ),
        )

    return _ItemResolution(
        item=None,
        check=FabricPreflightCheck(
            code=f"FABRIC_{item_type.upper()}_NOT_FOUND",
            status="BLOCKED" if required else "WARNING",
            message=f"Fabric {item_type} item was not found.",
        ),
    )


def _spark_settings_checks(*, client: FabricRestClient, capacity_id: str) -> tuple[FabricPreflightCheck, ...]:
    checks: list[FabricPreflightCheck] = []
    capacity = _capacity_by_id(client, capacity_id)
    if capacity is None:
        checks.append(
            FabricPreflightCheck(
                code="FABRIC_CAPACITY_DETAILS_UNAVAILABLE",
                status="WARNING",
                message="Fabric capacity details could not be resolved.",
                details={"capacity_id": capacity_id},
            )
        )
    else:
        checks.append(
            FabricPreflightCheck(
                code="FABRIC_CAPACITY_DETAILS_RESOLVED",
                status="OK",
                message="Fabric capacity details are readable.",
                details={
                    "capacity_id": capacity.get("id"),
                    "sku": capacity.get("sku"),
                    "region": capacity.get("region"),
                    "state": capacity.get("state"),
                },
            )
        )

    try:
        settings, _etag = client.get_spark_settings()
        pools = client.list_spark_pools()
    except FabricRestError as exc:
        return (
            *checks,
            FabricPreflightCheck(
                code="FABRIC_SPARK_SETTINGS_UNAVAILABLE",
                status="WARNING",
                message=str(exc),
            ),
        )

    default_pool = _default_spark_pool(settings)
    starter_pool = next((pool for pool in pools if _is_starter_pool(pool)), None)
    details = {
        "capacity_sku": None if capacity is None else capacity.get("sku"),
        "default_pool": default_pool,
        "starter_pool": _pool_details(starter_pool),
    }
    if _is_ftl4(capacity) and _is_default_starter_pool(default_pool) and _is_medium_or_larger(starter_pool):
        return (
            *checks,
            FabricPreflightCheck(
                code="FABRIC_SPARK_POOL_OVERSIZED_FOR_FTL4",
                status="WARNING",
                message=(
                    "Workspace default Spark pool uses Starter Pool Medium on FTL4; "
                    "use a Small single-node custom pool for reliable smoke execution."
                ),
                details=details,
            ),
        )

    return (
        *checks,
        FabricPreflightCheck(
            code="FABRIC_SPARK_POOL_COMPATIBLE",
            status="OK",
            message="Fabric Spark default pool is compatible with the detected capacity for smoke execution.",
            details=details,
        ),
    )


def _notebook_jobs_check(*, client: FabricRestClient, notebook: dict[str, Any] | None) -> FabricPreflightCheck:
    if notebook is None:
        return FabricPreflightCheck(
            code="FABRIC_NOTEBOOK_JOBS_SKIPPED",
            status="WARNING",
            message="Notebook job history was not checked because the notebook item was not resolved.",
        )
    notebook_id = notebook.get("id")
    if not isinstance(notebook_id, str) or not notebook_id:
        return FabricPreflightCheck(
            code="FABRIC_NOTEBOOK_JOBS_SKIPPED",
            status="WARNING",
            message="Notebook job history was not checked because the notebook item did not include an id.",
            details=_item_details(notebook),
        )
    try:
        jobs = client.list_job_instances(item_id=notebook_id)
    except FabricRestError as exc:
        return FabricPreflightCheck(
            code="FABRIC_NOTEBOOK_JOBS_UNAVAILABLE",
            status="WARNING",
            message=str(exc),
            details={"notebook_id": notebook_id},
        )

    active_jobs = [job for job in jobs if _is_active_job_status(job)]
    details = {
        "notebook_id": notebook_id,
        "job_count": len(jobs),
        "active_job_count": len(active_jobs),
        "active_jobs": [_job_details(job) for job in active_jobs[:10]],
        "latest_jobs": [_job_details(job) for job in jobs[:10]],
    }
    if active_jobs:
        return FabricPreflightCheck(
            code="FABRIC_NOTEBOOK_ACTIVE_JOBS",
            status="WARNING",
            message="Fabric notebook has active job instances that can consume Spark capacity.",
            details=details,
        )
    return FabricPreflightCheck(
        code="FABRIC_NOTEBOOK_NO_ACTIVE_JOBS",
        status="OK",
        message="Fabric notebook has no active job instances.",
        details=details,
    )


def _capacity_by_id(client: FabricRestClient, capacity_id: str) -> dict[str, Any] | None:
    try:
        capacities = client.list_capacities()
    except FabricRestError:
        return None
    return next((capacity for capacity in capacities if capacity.get("id") == capacity_id), None)


def _default_spark_pool(settings: dict[str, Any]) -> dict[str, Any] | None:
    pool = settings.get("pool") if isinstance(settings.get("pool"), dict) else {}
    default_pool = pool.get("defaultPool") if isinstance(pool.get("defaultPool"), dict) else None
    return default_pool


def _pool_details(pool: dict[str, Any] | None) -> dict[str, Any] | None:
    if pool is None:
        return None
    return {
        "id": pool.get("id"),
        "name": pool.get("name"),
        "node_family": pool.get("nodeFamily"),
        "node_size": pool.get("nodeSize"),
        "auto_scale": pool.get("autoScale"),
        "dynamic_executor_allocation": pool.get("dynamicExecutorAllocation"),
    }


def _is_starter_pool(pool: dict[str, Any]) -> bool:
    return str(pool.get("name") or "").casefold() == "starter pool"


def _is_default_starter_pool(pool: dict[str, Any] | None) -> bool:
    if not pool:
        return False
    name = str(pool.get("name") or "").casefold()
    pool_id = str(pool.get("id") or "")
    return name == "starter pool" or pool_id == "00000000-0000-0000-0000-000000000000"


def _is_ftl4(capacity: dict[str, Any] | None) -> bool:
    return bool(capacity and str(capacity.get("sku") or "").casefold() == "ftl4")


def _is_medium_or_larger(pool: dict[str, Any] | None) -> bool:
    if pool is None:
        return False
    size = str(pool.get("nodeSize") or "").casefold()
    return size in {"medium", "large", "xlarge", "xxlarge"}


def _workspace_details(workspace: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": workspace.get("id"),
        "display_name": workspace.get("displayName"),
        "type": workspace.get("type"),
        "capacity_id": workspace.get("capacityId"),
        "capacity_assignment_progress": workspace.get("capacityAssignmentProgress"),
        "capacity_region": workspace.get("capacityRegion"),
    }


def _item_details(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "display_name": item.get("displayName"),
        "type": item.get("type"),
        "workspace_id": item.get("workspaceId"),
        "folder_id": item.get("folderId"),
    }


def _job_details(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "item_id": job.get("itemId"),
        "job_type": job.get("jobType"),
        "invoke_type": job.get("invokeType"),
        "status": job.get("status"),
        "start_time_utc": job.get("startTimeUtc"),
        "end_time_utc": job.get("endTimeUtc"),
    }


def _is_active_job_status(job: dict[str, Any]) -> bool:
    status = str(job.get("status") or "").casefold().replace("_", "").replace(" ", "")
    return status in {
        "accepted",
        "cancelling",
        "inprogress",
        "notstarted",
        "pending",
        "queued",
        "running",
    }


def _preflight_status(checks: list[FabricPreflightCheck]) -> str:
    if any(check.status == "BLOCKED" for check in checks):
        return "BLOCKED"
    if any(check.status == "WARNING" for check in checks):
        return "OK_WITH_WARNINGS"
    return "OK"
