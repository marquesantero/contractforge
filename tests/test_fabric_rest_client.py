from __future__ import annotations

import json

import pytest

from contractforge_fabric.runtime import (
    FabricHttpRequest,
    FabricHttpResponse,
    FabricOperation,
    FabricRestClient,
    FabricRestError,
    fabric_job_reference_from_url,
    fabric_rest_client_from_environment,
)


class FakeTransport:
    def __init__(self, responses: list[FabricHttpResponse]) -> None:
        self.responses = responses
        self.requests: list[FabricHttpRequest] = []

    def __call__(self, request: FabricHttpRequest) -> FabricHttpResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("Unexpected Fabric request")
        return self.responses.pop(0)


def _json_response(
    status: int,
    payload: dict[str, object],
    headers: dict[str, str] | None = None,
) -> FabricHttpResponse:
    return FabricHttpResponse(
        status_code=status,
        headers=headers or {},
        body=json.dumps(payload).encode("utf-8"),
    )


def test_create_notebook_renders_fabric_rest_request_and_lro_metadata() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=202,
                headers={
                    "Location": "https://api.fabric.microsoft.com/v1/operations/op-1",
                    "x-ms-operation-id": "op-1",
                    "Retry-After": "5",
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    operation = client.create_notebook(
        display_name="cf_orders",
        description="Review notebook",
        definition={"format": "fabricGitSource", "parts": []},
    )

    assert operation == FabricOperation(
        location="https://api.fabric.microsoft.com/v1/operations/op-1",
        operation_id="op-1",
        retry_after_seconds=5,
    )
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url == "https://api.fabric.microsoft.com/v1/workspaces/workspace-1/notebooks"
    assert request.headers["Authorization"] == "Bearer token-1"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads((request.body or b"").decode("utf-8")) == {
        "displayName": "cf_orders",
        "description": "Review notebook",
        "definition": {"format": "fabricGitSource", "parts": []},
    }


def test_create_lakehouse_renders_fabric_rest_request() -> None:
    transport = FakeTransport([_json_response(201, {"id": "lakehouse-1", "displayName": "contractforge_lh"})])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = client.create_lakehouse(
        display_name="contractforge_lh",
        description="ContractForge Fabric test Lakehouse.",
    )

    assert result == {"id": "lakehouse-1", "displayName": "contractforge_lh"}
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url == "https://api.fabric.microsoft.com/v1/workspaces/workspace-1/lakehouses"
    assert json.loads((request.body or b"").decode("utf-8")) == {
        "displayName": "contractforge_lh",
        "description": "ContractForge Fabric test Lakehouse.",
    }


def test_create_shortcut_renders_fabric_rest_request() -> None:
    transport = FakeTransport(
        [
            _json_response(
                201,
                {
                    "path": "Files/source-expansion/shortcuts",
                    "name": "orc_orders_shortcut",
                    "target": {
                        "type": "OneLake",
                        "oneLake": {
                            "workspaceId": "source-workspace",
                            "itemId": "source-lakehouse",
                            "path": "Files/source-expansion/lakehouse-file-formats/orc_orders",
                        },
                    },
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace/1", access_token="token-1", transport=transport)

    result = client.create_shortcut(
        item_id="lakehouse/1",
        path="Files/source-expansion/shortcuts",
        name="orc_orders_shortcut",
        conflict_policy="CreateOrOverwrite",
        target={
            "oneLake": {
                "workspaceId": "source-workspace",
                "itemId": "source-lakehouse",
                "path": "Files/source-expansion/lakehouse-file-formats/orc_orders",
            }
        },
    )

    assert result["name"] == "orc_orders_shortcut"
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith(
        "/workspaces/workspace%2F1/items/lakehouse%2F1/shortcuts?shortcutConflictPolicy=CreateOrOverwrite"
    )
    assert json.loads((request.body or b"").decode("utf-8")) == {
        "path": "Files/source-expansion/shortcuts",
        "name": "orc_orders_shortcut",
        "target": {
            "oneLake": {
                "workspaceId": "source-workspace",
                "itemId": "source-lakehouse",
                "path": "Files/source-expansion/lakehouse-file-formats/orc_orders",
            }
        },
    }


def test_list_shortcuts_collects_values() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {
                    "value": [
                        {"path": "Files/source-expansion/shortcuts", "name": "orc_orders_shortcut"}
                    ]
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = client.list_shortcuts(item_id="lakehouse-1", path="Files/source-expansion/shortcuts")

    assert result == [{"path": "Files/source-expansion/shortcuts", "name": "orc_orders_shortcut"}]
    assert transport.requests[0].method == "GET"
    assert transport.requests[0].url.endswith(
        "/workspaces/workspace-1/items/lakehouse-1/shortcuts?path=Files%2Fsource-expansion%2Fshortcuts"
    )


def test_list_capacities_uses_fabric_capacity_endpoint() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {
                    "value": [
                        {
                            "id": "capacity-1",
                            "displayName": "Trial",
                            "sku": "FTL4",
                            "state": "Active",
                        }
                    ]
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    assert client.list_capacities() == [
        {"id": "capacity-1", "displayName": "Trial", "sku": "FTL4", "state": "Active"}
    ]
    assert transport.requests[0].url.endswith("/capacities")


def test_spark_pool_and_settings_endpoints_support_ftl4_mitigation() -> None:
    transport = FakeTransport(
        [
            _json_response(200, {"value": [{"id": "starter", "name": "Starter Pool", "nodeSize": "Medium"}]}),
            _json_response(
                201,
                {
                    "id": "pool-1",
                    "name": "cf_small_single_node",
                    "nodeFamily": "MemoryOptimized",
                    "nodeSize": "Small",
                },
            ),
            _json_response(
                200,
                {
                    "pool": {
                        "defaultPool": {"id": "starter", "name": "Starter Pool", "type": "Workspace"},
                        "starterPool": {"maxNodeCount": 10, "maxExecutors": 9},
                    }
                },
                headers={"ETag": '"etag-1"'},
            ),
            _json_response(
                200,
                {
                    "pool": {
                        "defaultPool": {
                            "id": "pool-1",
                            "name": "cf_small_single_node",
                            "type": "Workspace",
                        },
                        "starterPool": {"maxNodeCount": 10, "maxExecutors": 9},
                    }
                },
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    assert client.list_spark_pools() == [{"id": "starter", "name": "Starter Pool", "nodeSize": "Medium"}]
    pool = client.create_spark_pool(name="cf_small_single_node")
    settings, etag = client.get_spark_settings()
    settings["pool"]["defaultPool"] = {"id": pool["id"], "name": pool["name"], "type": "Workspace"}
    updated = client.update_spark_settings(settings, etag=etag)

    assert pool["nodeSize"] == "Small"
    assert etag == '"etag-1"'
    assert updated["pool"]["defaultPool"]["id"] == "pool-1"
    assert transport.requests[0].url.endswith("/workspaces/workspace-1/spark/pools")
    assert transport.requests[1].url.endswith("/workspaces/workspace-1/spark/pools")
    assert json.loads((transport.requests[1].body or b"").decode("utf-8")) == {
        "name": "cf_small_single_node",
        "nodeFamily": "MemoryOptimized",
        "nodeSize": "Small",
        "autoScale": {"enabled": False, "minNodeCount": 1, "maxNodeCount": 1},
        "dynamicExecutorAllocation": {"enabled": False},
    }
    assert transport.requests[2].url.endswith("/workspaces/workspace-1/spark/settings")
    assert transport.requests[3].method == "PATCH"
    assert transport.requests[3].headers["If-Match"] == '"etag-1"'


def test_update_notebook_definition_uses_documented_endpoint() -> None:
    transport = FakeTransport([_json_response(200, {"id": "notebook-1"})])
    client = FabricRestClient(workspace_id="workspace/1", access_token="token-1", transport=transport)

    result = client.update_notebook_definition(
        notebook_id="notebook/1",
        definition={"format": "fabricGitSource", "parts": []},
    )

    assert result == {"id": "notebook-1"}
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith(
        "/workspaces/workspace%2F1/notebooks/notebook%2F1/updateDefinition?updateMetadata=True"
    )
    assert json.loads((request.body or b"").decode("utf-8")) == {
        "definition": {"format": "fabricGitSource", "parts": []}
    }


def test_get_notebook_definition_uses_documented_endpoint() -> None:
    transport = FakeTransport([_json_response(200, {"definition": {"parts": []}})])
    client = FabricRestClient(workspace_id="workspace/1", access_token="token-1", transport=transport)

    result = client.get_notebook_definition(notebook_id="notebook/1")

    assert result == {"definition": {"parts": []}}
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith(
        "/workspaces/workspace%2F1/notebooks/notebook%2F1/getDefinition?format=fabricGitSource"
    )
    assert request.body is None


def test_get_notebook_definition_follows_lro_result_endpoint() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=202,
                headers={
                    "Location": "https://api.fabric.microsoft.com/v1/operations/op-1",
                    "x-ms-operation-id": "op-1",
                    "Retry-After": "1",
                },
            ),
            _json_response(200, {"status": "Succeeded", "percentComplete": 100}),
            _json_response(200, {"definition": {"format": "fabricGitSource", "parts": []}}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = client.get_notebook_definition(notebook_id="notebook-1", sleep=None)

    assert result == {"definition": {"format": "fabricGitSource", "parts": []}}
    assert transport.requests[0].method == "POST"
    assert transport.requests[0].url.endswith(
        "/workspaces/workspace-1/notebooks/notebook-1/getDefinition?format=fabricGitSource"
    )
    assert transport.requests[1].method == "GET"
    assert transport.requests[1].url == "https://api.fabric.microsoft.com/v1/operations/op-1"
    assert transport.requests[2].method == "GET"
    assert transport.requests[2].url == "https://api.fabric.microsoft.com/v1/operations/op-1/result"


def test_run_notebook_uses_execute_job_endpoint_and_default_beta_false() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=202,
                headers={
                    "Location": "https://api.fabric.microsoft.com/v1/jobs/instances/job-1",
                    "Retry-After": "60",
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    operation = client.run_notebook(
        notebook_id="notebook-1",
        execution_data={"compute": "Jupyter"},
        parameters=[{"name": "run_id", "value": "run-1"}],
    )

    assert operation.location == "https://api.fabric.microsoft.com/v1/jobs/instances/job-1"
    assert operation.retry_after_seconds == 60
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith("/workspaces/workspace-1/notebooks/notebook-1/jobs/execute/instances?beta=false")
    assert json.loads((request.body or b"").decode("utf-8")) == {
        "executionData": {"compute": "Jupyter"},
        "parameters": [{"name": "run_id", "value": "run-1"}],
    }


def test_job_reference_from_url_extracts_ids() -> None:
    ref = fabric_job_reference_from_url(
        "https://api.fabric.microsoft.com/v1/workspaces/workspace-1/items/item-1/jobs/instances/job-1"
    )

    assert ref.workspace_id == "workspace-1"
    assert ref.item_id == "item-1"
    assert ref.job_instance_id == "job-1"


def test_get_job_instance_uses_core_job_scheduler_endpoint() -> None:
    transport = FakeTransport([_json_response(200, {"id": "job-1", "status": "Completed"})])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = client.get_job_instance(item_id="item-1", job_instance_id="job-1")

    assert result == {"id": "job-1", "status": "Completed"}
    assert transport.requests[0].method == "GET"
    assert transport.requests[0].url.endswith("/workspaces/workspace-1/items/item-1/jobs/instances/job-1")


def test_list_job_instances_uses_core_job_scheduler_endpoint() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {
                    "value": [
                        {"id": "job-1", "status": "Running"},
                        {"id": "job-2", "status": "Completed"},
                    ]
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = client.list_job_instances(item_id="item-1")

    assert result == [
        {"id": "job-1", "status": "Running"},
        {"id": "job-2", "status": "Completed"},
    ]
    assert transport.requests[0].method == "GET"
    assert transport.requests[0].url.endswith("/workspaces/workspace-1/items/item-1/jobs/instances")


def test_list_active_job_instances_filters_terminal_statuses() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {
                    "value": [
                        {"id": "job-1", "status": "NotStarted"},
                        {"id": "job-2", "status": "Running"},
                        {"id": "job-3", "status": "Failed"},
                        {"id": "job-4", "status": "Completed"},
                        {"id": "job-5", "status": "Queued"},
                    ]
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    assert client.list_active_job_instances(item_id="item-1") == [
        {"id": "job-1", "status": "NotStarted"},
        {"id": "job-2", "status": "Running"},
        {"id": "job-5", "status": "Queued"},
    ]


def test_cancel_job_instance_returns_lro_metadata() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=202,
                headers={
                    "Location": "https://api.fabric.microsoft.com/v1/workspaces/workspace-1/items/item-1/jobs/instances/job-1",
                    "Retry-After": "15",
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    operation = client.cancel_job_instance(item_id="item-1", job_instance_id="job-1")

    assert isinstance(operation, FabricOperation)
    assert operation.retry_after_seconds == 15
    assert transport.requests[0].method == "POST"
    assert transport.requests[0].url.endswith("/workspaces/workspace-1/items/item-1/jobs/instances/job-1/cancel")


def test_wait_job_instance_waits_until_terminal_status() -> None:
    transport = FakeTransport(
        [
            _json_response(200, {"id": "job-1", "status": "NotStarted"}),
            _json_response(200, {"id": "job-1", "status": "Running"}),
            _json_response(200, {"id": "job-1", "status": "Completed"}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)
    sleeps: list[float] = []

    result = client.wait_job_instance(
        item_id="item-1",
        job_instance_id="job-1",
        max_attempts=3,
        retry_after_seconds=2,
        sleep=sleeps.append,
    )

    assert result == {"id": "job-1", "status": "Completed"}
    assert sleeps == [2.0, 2.0]


def test_poll_operation_honors_retry_after_and_429() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(status_code=202, headers={"Retry-After": "2"}),
            FabricHttpResponse(status_code=429, headers={"Retry-After": "3"}),
            _json_response(200, {"status": "Succeeded"}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)
    sleeps: list[float] = []

    result = client.poll_operation(
        FabricOperation(
            location="https://api.fabric.microsoft.com/v1/operations/op-1",
            retry_after_seconds=1,
        ),
        max_attempts=3,
        sleep=sleeps.append,
    )

    assert result == {"status": "Succeeded"}
    assert sleeps == [1.0, 2.0, 3.0]
    assert [request.method for request in transport.requests] == ["GET", "GET", "GET"]


def test_poll_operation_fails_after_max_attempts() -> None:
    transport = FakeTransport([FabricHttpResponse(status_code=202, headers={})])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    with pytest.raises(FabricRestError, match="did not finish"):
        client.poll_operation(
            FabricOperation(location="https://api.fabric.microsoft.com/v1/operations/op-1"),
            max_attempts=1,
            sleep=None,
        )


def test_request_error_preserves_status_code() -> None:
    transport = FakeTransport([_json_response(403, {"error": {"code": "Forbidden"}})])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    with pytest.raises(FabricRestError) as exc:
        client.create_notebook(display_name="cf_orders", definition={"format": "fabricGitSource", "parts": []})

    assert exc.value.status_code == 403
    assert "Forbidden" in str(exc.value)


def test_list_workspaces_collects_continuation_pages() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {
                    "value": [{"id": "workspace-1", "displayName": "One"}],
                    "continuationUri": "https://api.fabric.microsoft.com/v1/workspaces?continuationToken=abc",
                },
            ),
            _json_response(200, {"value": [{"id": "workspace-2", "displayName": "Two"}]}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    workspaces = client.list_workspaces()

    assert workspaces == [
        {"id": "workspace-1", "displayName": "One"},
        {"id": "workspace-2", "displayName": "Two"},
    ]
    assert transport.requests[0].url.endswith("/workspaces?preferWorkspaceSpecificEndpoints=True")
    assert transport.requests[1].url.endswith("/workspaces?continuationToken=abc")


def test_resolve_workspace_id_requires_unique_display_name() -> None:
    transport = FakeTransport([_json_response(200, {"value": [{"id": "workspace-1", "displayName": "CF Dev"}]})])
    client = FabricRestClient(workspace_id="bootstrap", access_token="token-1", transport=transport)

    assert client.resolve_workspace_id("cf dev") == "workspace-1"


def test_list_items_supports_type_filter_and_include() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {
                    "value": [
                        {
                            "id": "lakehouse-1",
                            "displayName": "contractforge_lh",
                            "type": "Lakehouse",
                        }
                    ]
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    items = client.list_items(item_type="Lakehouse", include=("DefaultIdentity",))

    assert items == [{"id": "lakehouse-1", "displayName": "contractforge_lh", "type": "Lakehouse"}]
    assert transport.requests[0].url.endswith(
        "/workspaces/workspace-1/items?recursive=true&type=Lakehouse&include=DefaultIdentity"
    )


def test_resolve_item_id_uses_type_and_display_name() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {
                    "value": [
                        {
                            "id": "notebook-1",
                            "displayName": "cf_orders",
                            "type": "Notebook",
                        }
                    ]
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    assert client.resolve_item_id(item_type="Notebook", display_name="CF_ORDERS") == "notebook-1"


def test_fabric_rest_client_from_environment_uses_workspace_and_token_provider() -> None:
    transport = FakeTransport([_json_response(200, {"value": []})])
    client = fabric_rest_client_from_environment(
        {
            "parameters": {
                "fabric": {
                    "tenant_id": "00000000-0000-0000-0000-000000000000",
                    "workspace_id": "workspace-1",
                }
            }
        },
        token_provider=lambda: "token-1",
        transport=transport,
    )

    assert client.list_workspaces() == []
    assert transport.requests[0].headers["Authorization"] == "Bearer token-1"


def test_client_requires_workspace_and_token() -> None:
    with pytest.raises(ValueError, match="workspace_id"):
        FabricRestClient(workspace_id="", access_token="token-1", transport=FakeTransport([]))
    with pytest.raises(ValueError, match="access_token or token_provider"):
        FabricRestClient(workspace_id="workspace-1", transport=FakeTransport([]))
