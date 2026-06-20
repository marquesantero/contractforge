"""Small Fabric REST client primitives.

The client is intentionally dependency-free and transport-injectable so LRO,
throttling and request-shape behavior can be tested without Fabric credentials.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import urlencode, quote, urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FabricHttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None = None


@dataclass(frozen=True)
class FabricHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes = b""

    def json(self) -> Any:
        if not self.body:
            return None
        return json.loads(self.body.decode("utf-8"))


@dataclass(frozen=True)
class FabricOperation:
    location: str
    operation_id: str | None = None
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class FabricJobReference:
    workspace_id: str
    item_id: str
    job_instance_id: str


class FabricTransport(Protocol):
    def __call__(self, request: FabricHttpRequest) -> FabricHttpResponse:
        """Send a Fabric HTTP request."""


class FabricRestError(RuntimeError):
    def __init__(self, message: str, *, response: FabricHttpResponse | None = None) -> None:
        super().__init__(message)
        self.response = response

    @property
    def status_code(self) -> int | None:
        return None if self.response is None else self.response.status_code


TokenProvider = Callable[[], str]
Sleep = Callable[[float], None]


class FabricRestClient:
    """Minimal Fabric REST client for deploy-path hardening."""

    def __init__(
        self,
        *,
        workspace_id: str,
        access_token: str | None = None,
        token_provider: TokenProvider | None = None,
        base_url: str = "https://api.fabric.microsoft.com/v1",
        transport: FabricTransport | None = None,
    ) -> None:
        if not workspace_id:
            raise ValueError("Fabric workspace_id is required for REST operations")
        if access_token is None and token_provider is None:
            raise ValueError("Fabric REST operations require access_token or token_provider")
        self.workspace_id = workspace_id
        self._access_token = access_token
        self._token_provider = token_provider
        self.base_url = base_url.rstrip("/")
        self._transport = transport or _urllib_transport

    def create_notebook(
        self,
        *,
        display_name: str,
        definition: Mapping[str, Any],
        description: str | None = None,
    ) -> FabricOperation | dict[str, Any]:
        payload: dict[str, Any] = {
            "displayName": display_name,
            "definition": definition,
        }
        if description is not None:
            payload["description"] = description
        response = self.request_json(
            "POST",
            f"/workspaces/{_url_part(self.workspace_id)}/notebooks",
            payload,
            expected=(200, 201, 202),
        )
        if response.status_code == 202:
            return _operation_from_response(response)
        value = response.json()
        return value if isinstance(value, dict) else {}

    def create_lakehouse(
        self,
        *,
        display_name: str,
        description: str | None = None,
    ) -> FabricOperation | dict[str, Any]:
        payload: dict[str, Any] = {"displayName": display_name}
        if description is not None:
            payload["description"] = description
        response = self.request_json(
            "POST",
            f"/workspaces/{_url_part(self.workspace_id)}/lakehouses",
            payload,
            expected=(200, 201, 202),
        )
        if response.status_code == 202:
            return _operation_from_response(response)
        value = response.json()
        return value if isinstance(value, dict) else {}

    def create_shortcut(
        self,
        *,
        item_id: str,
        path: str,
        name: str,
        target: Mapping[str, Any],
        conflict_policy: str | None = None,
    ) -> dict[str, Any]:
        query = f"?shortcutConflictPolicy={_url_part(conflict_policy)}" if conflict_policy else ""
        response = self.request_json(
            "POST",
            f"/workspaces/{_url_part(self.workspace_id)}/items/{_url_part(item_id)}/shortcuts{query}",
            {"path": path, "name": name, "target": dict(target)},
            expected=(200, 201),
        )
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric shortcut response was not a JSON object", response=response)
        return value

    def list_shortcuts(
        self,
        *,
        item_id: str,
        path: str | None = None,
    ) -> list[dict[str, Any]]:
        query = f"?path={urlencode({'': path})[1:]}" if path else ""
        response = self.request(
            "GET",
            f"/workspaces/{_url_part(self.workspace_id)}/items/{_url_part(item_id)}/shortcuts{query}",
            expected=(200,),
        )
        return self._collect_paged_values(response)

    def list_capacities(self) -> list[dict[str, Any]]:
        response = self.request("GET", "/capacities", expected=(200,))
        return self._collect_paged_values(response)

    def list_spark_pools(self) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/workspaces/{_url_part(self.workspace_id)}/spark/pools",
            expected=(200,),
        )
        return self._collect_paged_values(response)

    def create_spark_pool(
        self,
        *,
        name: str,
        node_size: str = "Small",
        node_family: str = "MemoryOptimized",
        auto_scale: Mapping[str, Any] | None = None,
        dynamic_executor_allocation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "name": name,
            "nodeFamily": node_family,
            "nodeSize": node_size,
            "autoScale": dict(auto_scale or {"enabled": False, "minNodeCount": 1, "maxNodeCount": 1}),
            "dynamicExecutorAllocation": dict(dynamic_executor_allocation or {"enabled": False}),
        }
        response = self.request_json(
            "POST",
            f"/workspaces/{_url_part(self.workspace_id)}/spark/pools",
            payload,
            expected=(200, 201),
        )
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric Spark pool response was not a JSON object", response=response)
        return value

    def get_spark_settings(self) -> tuple[dict[str, Any], str | None]:
        response = self.request(
            "GET",
            f"/workspaces/{_url_part(self.workspace_id)}/spark/settings",
            expected=(200,),
        )
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric Spark settings response was not a JSON object", response=response)
        return value, _header(response.headers, "ETag")

    def update_spark_settings(
        self,
        settings: Mapping[str, Any],
        *,
        etag: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if etag:
            headers["If-Match"] = etag
        response = self.request(
            "PATCH",
            f"/workspaces/{_url_part(self.workspace_id)}/spark/settings",
            body=json.dumps(settings, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            expected=(200,),
        )
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric Spark settings update response was not a JSON object", response=response)
        return value

    def list_workspaces(self, *, prefer_workspace_specific_endpoints: bool = True) -> list[dict[str, Any]]:
        suffix = "True" if prefer_workspace_specific_endpoints else "False"
        response = self.request(
            "GET",
            f"/workspaces?preferWorkspaceSpecificEndpoints={suffix}",
            expected=(200,),
        )
        return self._collect_paged_values(response)

    def create_workspace(
        self,
        *,
        display_name: str,
        capacity_id: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"displayName": display_name}
        if capacity_id:
            payload["capacityId"] = capacity_id
        if description is not None:
            payload["description"] = description
        response = self.request_json("POST", "/workspaces", payload, expected=(201,))
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric workspace create response was not a JSON object", response=response)
        return value

    def get_workspace(
        self,
        workspace_id: str | None = None,
        *,
        prefer_workspace_specific_endpoints: bool = True,
    ) -> dict[str, Any]:
        suffix = "True" if prefer_workspace_specific_endpoints else "False"
        response = self.request(
            "GET",
            f"/workspaces/{_url_part(workspace_id or self.workspace_id)}?preferWorkspaceSpecificEndpoints={suffix}",
            expected=(200,),
        )
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric workspace response was not a JSON object", response=response)
        return value

    def resolve_workspace_id(self, workspace_name: str) -> str:
        matches = [
            workspace
            for workspace in self.list_workspaces()
            if str(workspace.get("displayName") or "").casefold() == workspace_name.casefold()
        ]
        if not matches:
            raise FabricRestError(f"Fabric workspace `{workspace_name}` was not found")
        if len(matches) > 1:
            raise FabricRestError(f"Fabric workspace `{workspace_name}` is not unique")
        workspace_id = matches[0].get("id")
        if not isinstance(workspace_id, str) or not workspace_id:
            raise FabricRestError(f"Fabric workspace `{workspace_name}` did not include an id")
        return workspace_id

    def list_items(
        self,
        *,
        item_type: str | None = None,
        include: tuple[str, ...] = (),
        recursive: bool = True,
    ) -> list[dict[str, Any]]:
        query: dict[str, str] = {"recursive": "true" if recursive else "false"}
        if item_type:
            query["type"] = item_type
        if include:
            query["include"] = ",".join(include)
        response = self.request(
            "GET",
            f"/workspaces/{_url_part(self.workspace_id)}/items?{urlencode(query)}",
            expected=(200,),
        )
        return self._collect_paged_values(response)

    def resolve_item_id(self, *, item_type: str, display_name: str) -> str:
        matches = [
            item
            for item in self.list_items(item_type=item_type)
            if str(item.get("displayName") or "").casefold() == display_name.casefold()
        ]
        if not matches:
            raise FabricRestError(f"Fabric {item_type} item `{display_name}` was not found")
        if len(matches) > 1:
            raise FabricRestError(f"Fabric {item_type} item `{display_name}` is not unique")
        item_id = matches[0].get("id")
        if not isinstance(item_id, str) or not item_id:
            raise FabricRestError(f"Fabric {item_type} item `{display_name}` did not include an id")
        return item_id

    def delete_item(self, *, item_id: str, hard_delete: bool = True) -> None:
        self.request(
            "DELETE",
            (
                f"/workspaces/{_url_part(self.workspace_id)}/items/{_url_part(item_id)}"
                f"?hardDelete={'True' if hard_delete else 'False'}"
            ),
            expected=(200, 202, 204),
        )

    def list_workspace_role_assignments(self) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/workspaces/{_url_part(self.workspace_id)}/roleAssignments",
            expected=(200,),
        )
        return self._collect_paged_values(response)

    def add_workspace_role_assignment(
        self,
        *,
        principal_id: str,
        principal_type: str,
        role: str,
    ) -> dict[str, Any]:
        response = self.request_json(
            "POST",
            f"/workspaces/{_url_part(self.workspace_id)}/roleAssignments",
            {"principal": {"id": principal_id, "type": principal_type}, "role": role},
            expected=(200, 201),
        )
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric workspace role assignment response was not a JSON object", response=response)
        return value

    def update_workspace_role_assignment(
        self,
        *,
        role_assignment_id: str,
        role: str,
    ) -> dict[str, Any]:
        response = self.request_json(
            "PATCH",
            (
                f"/workspaces/{_url_part(self.workspace_id)}/roleAssignments/"
                f"{_url_part(role_assignment_id)}"
            ),
            {"role": role},
            expected=(200,),
        )
        value = response.json()
        return value if isinstance(value, dict) else {}

    def delete_workspace_role_assignment(self, *, role_assignment_id: str) -> None:
        self.request(
            "DELETE",
            (
                f"/workspaces/{_url_part(self.workspace_id)}/roleAssignments/"
                f"{_url_part(role_assignment_id)}"
            ),
            expected=(200, 204),
        )

    def list_onelake_data_access_roles(self, *, item_id: str) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/workspaces/{_url_part(self.workspace_id)}/items/{_url_part(item_id)}/dataAccessRoles",
            expected=(200,),
        )
        return self._collect_paged_values(response)

    def create_or_update_onelake_data_access_role(
        self,
        *,
        item_id: str,
        role: Mapping[str, Any],
        conflict_policy: str = "Overwrite",
        preview: bool = True,
        etag: str | None = None,
        if_none_match: str | None = None,
    ) -> dict[str, Any]:
        query = urlencode(
            {
                "preview": "true" if preview else "false",
                "dataAccessRoleConflictPolicy": conflict_policy,
            }
        )
        headers = {"Content-Type": "application/json"}
        if etag:
            headers["If-Match"] = etag
        if if_none_match:
            headers["If-None-Match"] = if_none_match
        response = self.request(
            "POST",
            (
                f"/workspaces/{_url_part(self.workspace_id)}/items/{_url_part(item_id)}"
                f"/dataAccessRoles?{query}"
            ),
            body=json.dumps(dict(role), separators=(",", ":")).encode("utf-8"),
            headers=headers,
            expected=(200, 201),
        )
        value = response.json()
        return {
            "response": value if isinstance(value, dict) else {},
            "etag": _header(response.headers, "ETag"),
            "location": _header(response.headers, "Location"),
        }

    def delete_onelake_data_access_role(
        self,
        *,
        item_id: str,
        role_name: str,
        preview: bool = True,
    ) -> None:
        query = urlencode({"preview": "true" if preview else "false"})
        self.request(
            "DELETE",
            (
                f"/workspaces/{_url_part(self.workspace_id)}/items/{_url_part(item_id)}"
                f"/dataAccessRoles/{_url_part(role_name)}?{query}"
            ),
            expected=(200, 204),
        )

    def bulk_set_item_labels(
        self,
        *,
        items: list[Mapping[str, Any]],
        label_id: str,
        assignment_method: str | None = None,
        delegated_principal: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"items": [dict(item) for item in items], "labelId": label_id}
        if assignment_method:
            payload["assignmentMethod"] = assignment_method
        if delegated_principal:
            payload["delegatedPrincipal"] = dict(delegated_principal)
        response = self.request_json(
            "POST",
            "/admin/items/bulkSetLabels",
            payload,
            expected=(200, 202),
        )
        if response.status_code == 202:
            operation = _operation_from_response(response)
            return {
                "operation": {
                    "location": operation.location,
                    "operation_id": operation.operation_id,
                    "retry_after_seconds": operation.retry_after_seconds,
                }
            }
        value = response.json()
        return value if isinstance(value, dict) else {}

    def deploy_pipeline_stage_content(
        self,
        *,
        deployment_pipeline_id: str,
        source_stage_id: str,
        target_stage_id: str,
        items: list[Mapping[str, Any]] | None = None,
        note: str | None = None,
    ) -> FabricOperation:
        payload: dict[str, Any] = {
            "sourceStageId": source_stage_id,
            "targetStageId": target_stage_id,
        }
        if items is not None:
            payload["items"] = [dict(item) for item in items]
        if note:
            payload["note"] = note
        response = self.request_json(
            "POST",
            f"/deploymentPipelines/{_url_part(deployment_pipeline_id)}/deploy",
            payload,
            expected=(202,),
        )
        return _operation_from_response(response)

    def create_deployment_pipeline(
        self,
        *,
        display_name: str,
        stages: list[Mapping[str, Any]],
        description: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "displayName": display_name,
            "stages": [dict(stage) for stage in stages],
        }
        if description is not None:
            payload["description"] = description
        response = self.request_json(
            "POST",
            "/deploymentPipelines",
            payload,
            expected=(201,),
        )
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric deployment pipeline response was not a JSON object", response=response)
        return value

    def list_deployment_pipelines(self) -> list[dict[str, Any]]:
        response = self.request("GET", "/deploymentPipelines", expected=(200,))
        return self._collect_paged_values(response)

    def list_deployment_pipeline_stages(self, *, deployment_pipeline_id: str) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/deploymentPipelines/{_url_part(deployment_pipeline_id)}/stages",
            expected=(200,),
        )
        return self._collect_paged_values(response)

    def list_deployment_pipeline_stage_items(
        self,
        *,
        deployment_pipeline_id: str,
        stage_id: str,
    ) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/deploymentPipelines/{_url_part(deployment_pipeline_id)}/stages/{_url_part(stage_id)}/items",
            expected=(200,),
        )
        return self._collect_paged_values(response)

    def assign_workspace_to_deployment_pipeline_stage(
        self,
        *,
        deployment_pipeline_id: str,
        stage_id: str,
        workspace_id: str,
    ) -> None:
        self.request_json(
            "POST",
            (
                f"/deploymentPipelines/{_url_part(deployment_pipeline_id)}/stages/"
                f"{_url_part(stage_id)}/assignWorkspace"
            ),
            {"workspaceId": workspace_id},
            expected=(200,),
        )

    def unassign_workspace_from_deployment_pipeline_stage(
        self,
        *,
        deployment_pipeline_id: str,
        stage_id: str,
    ) -> None:
        self.request(
            "POST",
            (
                f"/deploymentPipelines/{_url_part(deployment_pipeline_id)}/stages/"
                f"{_url_part(stage_id)}/unassignWorkspace"
            ),
            expected=(200,),
        )

    def delete_deployment_pipeline(self, *, deployment_pipeline_id: str) -> None:
        self.request(
            "DELETE",
            f"/deploymentPipelines/{_url_part(deployment_pipeline_id)}",
            expected=(200, 204),
        )

    def connect_workspace_git(
        self,
        *,
        git_provider_details: Mapping[str, Any],
        git_credentials: Mapping[str, Any],
    ) -> dict[str, Any]:
        response = self.request_json(
            "POST",
            f"/workspaces/{_url_part(self.workspace_id)}/git/connect",
            {
                "gitProviderDetails": dict(git_provider_details),
                "myGitCredentials": dict(git_credentials),
            },
            expected=(200,),
        )
        value = response.json()
        return value if isinstance(value, dict) else {}

    def update_notebook_definition(
        self,
        *,
        notebook_id: str,
        definition: Mapping[str, Any],
        update_metadata: bool = True,
    ) -> FabricOperation | dict[str, Any]:
        metadata = "True" if update_metadata else "False"
        path = (
            f"/workspaces/{_url_part(self.workspace_id)}/notebooks/{_url_part(notebook_id)}"
            f"/updateDefinition?updateMetadata={metadata}"
        )
        response = self.request_json("POST", path, {"definition": definition}, expected=(200, 202))
        if response.status_code == 202:
            return _operation_from_response(response)
        value = response.json()
        return value if isinstance(value, dict) else {}

    def get_notebook_definition(
        self,
        *,
        notebook_id: str,
        format: str = "fabricGitSource",
        max_attempts: int = 30,
        sleep: Sleep | None = time.sleep,
    ) -> dict[str, Any]:
        path = (
            f"/workspaces/{_url_part(self.workspace_id)}/notebooks/{_url_part(notebook_id)}"
            f"/getDefinition?format={_url_part(format)}"
        )
        response = self.request("POST", path, expected=(200, 202))
        if response.status_code == 202:
            operation = _operation_from_response(response)
            operation_result = self.poll_operation(operation, max_attempts=max_attempts, sleep=sleep)
            if isinstance(operation_result.get("definition"), dict):
                return operation_result
            result_response = self.request(
                "GET",
                f"{operation.location.rstrip('/')}/result",
                absolute=True,
                expected=(200,),
            )
            value = result_response.json()
            if not isinstance(value, dict):
                raise FabricRestError("Fabric notebook definition result response was not a JSON object", response=result_response)
            return value
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric notebook definition response was not a JSON object", response=response)
        return value

    def run_notebook(
        self,
        *,
        notebook_id: str,
        execution_data: Mapping[str, Any] | None = None,
        parameters: list[Mapping[str, Any]] | None = None,
        beta: bool = False,
    ) -> FabricOperation:
        payload: dict[str, Any] = {}
        if execution_data is not None:
            payload["executionData"] = execution_data
        if parameters is not None:
            payload["parameters"] = parameters
        response = self.request_json(
            "POST",
            (
                f"/workspaces/{_url_part(self.workspace_id)}/notebooks/{_url_part(notebook_id)}"
                f"/jobs/execute/instances?beta={'true' if beta else 'false'}"
            ),
            payload,
            expected=(202,),
        )
        return _operation_from_response(response)

    def get_job_instance(
        self,
        *,
        item_id: str,
        job_instance_id: str,
    ) -> dict[str, Any]:
        response = self.request(
            "GET",
            (
                f"/workspaces/{_url_part(self.workspace_id)}/items/{_url_part(item_id)}"
                f"/jobs/instances/{_url_part(job_instance_id)}"
            ),
            expected=(200,),
        )
        value = response.json()
        if not isinstance(value, dict):
            raise FabricRestError("Fabric job instance response was not a JSON object", response=response)
        return value

    def list_job_instances(
        self,
        *,
        item_id: str,
    ) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            (
                f"/workspaces/{_url_part(self.workspace_id)}/items/{_url_part(item_id)}"
                "/jobs/instances"
            ),
            expected=(200,),
        )
        return self._collect_paged_values(response)

    def list_active_job_instances(
        self,
        *,
        item_id: str,
    ) -> list[dict[str, Any]]:
        return [
            instance
            for instance in self.list_job_instances(item_id=item_id)
            if _is_active_job_status(instance.get("status"))
        ]

    def cancel_job_instance(
        self,
        *,
        item_id: str,
        job_instance_id: str,
    ) -> FabricOperation | dict[str, Any]:
        response = self.request(
            "POST",
            (
                f"/workspaces/{_url_part(self.workspace_id)}/items/{_url_part(item_id)}"
                f"/jobs/instances/{_url_part(job_instance_id)}/cancel"
            ),
            expected=(200, 202),
        )
        if response.status_code == 202:
            return _operation_from_response(response)
        value = response.json()
        return value if isinstance(value, dict) else {}

    def wait_job_instance(
        self,
        *,
        item_id: str,
        job_instance_id: str,
        max_attempts: int = 30,
        retry_after_seconds: int = 60,
        sleep: Sleep | None = time.sleep,
    ) -> dict[str, Any]:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        for attempt in range(max_attempts):
            result = self.get_job_instance(item_id=item_id, job_instance_id=job_instance_id)
            status = str(result.get("status") or "").casefold()
            if status in {"completed", "succeeded", "failed", "cancelled", "canceled"}:
                return result
            if attempt + 1 < max_attempts and retry_after_seconds > 0 and sleep is not None:
                sleep(float(retry_after_seconds))
        raise FabricRestError(f"Fabric job instance `{job_instance_id}` did not finish after {max_attempts} attempts")

    def poll_operation(
        self,
        operation: FabricOperation,
        *,
        max_attempts: int = 30,
        sleep: Sleep | None = time.sleep,
    ) -> dict[str, Any]:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        retry_after = operation.retry_after_seconds
        for _attempt in range(max_attempts):
            if retry_after is not None and retry_after > 0 and sleep is not None:
                sleep(float(retry_after))
            response = self.request("GET", operation.location, absolute=True, expected=(200, 202, 429))
            if response.status_code == 429:
                retry_after = _retry_after(response.headers) or retry_after or 1
                continue
            if response.status_code == 202:
                retry_after = _retry_after(response.headers) or retry_after
                continue
            value = response.json()
            return value if isinstance(value, dict) else {}
        raise FabricRestError(f"Fabric operation did not finish after {max_attempts} attempts")

    def request_json(
        self,
        method: str,
        path_or_url: str,
        payload: Mapping[str, Any],
        *,
        expected: tuple[int, ...],
        absolute: bool = False,
    ) -> FabricHttpResponse:
        return self.request(
            method,
            path_or_url,
            body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            expected=expected,
            absolute=absolute,
        )

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        expected: tuple[int, ...],
        absolute: bool = False,
    ) -> FabricHttpResponse:
        url = path_or_url if absolute else f"{self.base_url}{path_or_url}"
        request_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token()}",
            **dict(headers or {}),
        }
        response = self._transport(
            FabricHttpRequest(
                method=method.upper(),
                url=url,
                headers=request_headers,
                body=body,
            ),
        )
        if response.status_code not in expected:
            raise FabricRestError(_error_message(response), response=response)
        return response

    def _collect_paged_values(self, first_response: FabricHttpResponse) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        response = first_response
        while True:
            payload = response.json()
            if not isinstance(payload, dict):
                raise FabricRestError("Fabric paged response was not a JSON object", response=response)
            page_values = payload.get("value") or []
            if not isinstance(page_values, list):
                raise FabricRestError("Fabric paged response `value` was not a list", response=response)
            values.extend(value for value in page_values if isinstance(value, dict))
            continuation_uri = payload.get("continuationUri")
            if not continuation_uri:
                return values
            if not isinstance(continuation_uri, str):
                raise FabricRestError("Fabric continuationUri was not a string", response=response)
            response = self.request("GET", continuation_uri, absolute=True, expected=(200,))

    def _token(self) -> str:
        token = self._token_provider() if self._token_provider is not None else self._access_token
        if not token:
            raise ValueError("Fabric access token provider returned an empty token")
        return token


def _operation_from_response(response: FabricHttpResponse) -> FabricOperation:
    location = _header(response.headers, "Location")
    if not location:
        raise FabricRestError("Fabric LRO response did not include a Location header", response=response)
    return FabricOperation(
        location=location,
        operation_id=_header(response.headers, "x-ms-operation-id"),
        retry_after_seconds=_retry_after(response.headers),
    )


def fabric_job_reference_from_url(url: str) -> FabricJobReference:
    parts = [part for part in urlparse(url).path.split("/") if part]
    try:
        workspaces_index = parts.index("workspaces")
        items_index = parts.index("items")
        instances_index = parts.index("instances")
    except ValueError as exc:
        raise ValueError(f"Not a Fabric item job instance URL: {url}") from exc
    try:
        return FabricJobReference(
            workspace_id=parts[workspaces_index + 1],
            item_id=parts[items_index + 1],
            job_instance_id=parts[instances_index + 1],
        )
    except IndexError as exc:
        raise ValueError(f"Incomplete Fabric item job instance URL: {url}") from exc


def _retry_after(headers: Mapping[str, str]) -> int | None:
    value = _header(headers, "Retry-After")
    if value is None:
        return None
    try:
        return max(0, int(value))
    except ValueError:
        return None


def _header(headers: Mapping[str, str], key: str) -> str | None:
    wanted = key.lower()
    for name, value in headers.items():
        if name.lower() == wanted:
            return value
    return None


def _is_active_job_status(status: Any) -> bool:
    return str(status or "").casefold().replace("_", "").replace(" ", "") in {
        "accepted",
        "cancelling",
        "inprogress",
        "notstarted",
        "pending",
        "queued",
        "running",
    }


def _error_message(response: FabricHttpResponse) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = None
    detail = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        detail = json.dumps(error if error is not None else payload, sort_keys=True)
    suffix = f": {detail}" if detail else ""
    return f"Fabric REST request failed with HTTP {response.status_code}{suffix}"


def _url_part(value: str) -> str:
    return quote(value, safe="")


def _urllib_transport(request: FabricHttpRequest) -> FabricHttpResponse:
    raw_request = Request(
        request.url,
        data=request.body,
        headers=dict(request.headers),
        method=request.method,
    )
    try:
        with urlopen(raw_request) as response:  # nosec B310 - FabricRestClient owns the base endpoint.
            return FabricHttpResponse(
                status_code=response.status,
                headers=dict(response.headers.items()),
                body=response.read(),
            )
    except HTTPError as exc:
        return FabricHttpResponse(
            status_code=exc.code,
            headers=dict(exc.headers.items()),
            body=exc.read(),
        )
