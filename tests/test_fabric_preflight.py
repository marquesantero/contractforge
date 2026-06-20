from __future__ import annotations

import json

from contractforge_fabric.runtime import (
    FabricHttpRequest,
    FabricHttpResponse,
    FabricRestClient,
    check_fabric_workspace_preflight,
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


def _json_response(payload: dict[str, object]) -> FabricHttpResponse:
    return FabricHttpResponse(
        status_code=200,
        headers={},
        body=json.dumps(payload).encode("utf-8"),
    )


def test_workspace_preflight_accepts_capacity_backed_workspace() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                    "capacityAssignmentProgress": "Completed",
                    "capacityRegion": "Brazil South",
                }
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {"parameters": {"fabric": {"workspace_id": "workspace-1"}}},
        client=client,
    )

    assert result.ok is True
    assert result.status == "OK"
    assert [check.code for check in result.checks] == [
        "FABRIC_WORKSPACE_READABLE",
        "FABRIC_WORKSPACE_CAPACITY_ASSIGNED",
    ]
    assert result.workspace and result.workspace["capacityId"] == "capacity-1"
    assert transport.requests[0].url.endswith(
        "/workspaces/workspace-1?preferWorkspaceSpecificEndpoints=True"
    )
    assert result.items == {}


def test_workspace_preflight_blocks_workspace_without_capacity() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "My workspace",
                    "type": "Personal",
                }
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {"parameters": {"fabric": {"workspace_id": "workspace-1"}}},
        client=client,
    )

    assert result.ok is False
    assert result.status == "BLOCKED"
    assert result.checks[-1].code == "FABRIC_WORKSPACE_CAPACITY_REQUIRED"


def test_workspace_preflight_resolves_workspace_by_name() -> None:
    transport = FakeTransport(
        [
            _json_response({"value": [{"id": "workspace-1", "displayName": "Manager"}]}),
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                }
            ),
        ]
    )
    client = FabricRestClient(workspace_id="bootstrap", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {"parameters": {"fabric": {"workspace_name": "Manager"}}},
        client=client,
    )

    assert result.ok is True
    assert result.checks[0].code == "FABRIC_WORKSPACE_RESOLVED_BY_NAME"
    assert result.checks[0].details == {"workspace_id": "workspace-1"}


def test_workspace_preflight_warns_when_ftl4_uses_medium_starter_pool() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                    "capacityAssignmentProgress": "Completed",
                }
            ),
            _json_response({"value": [{"id": "capacity-1", "sku": "FTL4", "region": "Brazil South"}]}),
            _json_response(
                {
                    "pool": {
                        "defaultPool": {
                            "id": "00000000-0000-0000-0000-000000000000",
                            "name": "Starter Pool",
                            "type": "Workspace",
                        }
                    }
                }
            ),
            _json_response(
                {
                    "value": [
                        {
                            "id": "00000000-0000-0000-0000-000000000000",
                            "name": "Starter Pool",
                            "nodeFamily": "MemoryOptimized",
                            "nodeSize": "Medium",
                        }
                    ]
                }
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {"parameters": {"fabric": {"workspace_id": "workspace-1"}}},
        client=client,
        check_spark_settings=True,
    )

    assert result.ok is True
    assert result.status == "OK_WITH_WARNINGS"
    assert [check.code for check in result.checks][-2:] == [
        "FABRIC_CAPACITY_DETAILS_RESOLVED",
        "FABRIC_SPARK_POOL_OVERSIZED_FOR_FTL4",
    ]
    assert result.checks[-1].details and result.checks[-1].details["capacity_sku"] == "FTL4"


def test_workspace_preflight_accepts_small_custom_pool_on_ftl4() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                    "capacityAssignmentProgress": "Completed",
                }
            ),
            _json_response({"value": [{"id": "capacity-1", "sku": "FTL4", "region": "Brazil South"}]}),
            _json_response(
                {
                    "pool": {
                        "defaultPool": {
                            "id": "pool-1",
                            "name": "cf_small_single_node",
                            "type": "Workspace",
                        }
                    }
                }
            ),
            _json_response(
                {
                    "value": [
                        {
                            "id": "pool-1",
                            "name": "cf_small_single_node",
                            "nodeFamily": "MemoryOptimized",
                            "nodeSize": "Small",
                        }
                    ]
                }
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {"parameters": {"fabric": {"workspace_id": "workspace-1"}}},
        client=client,
        check_spark_settings=True,
    )

    assert result.ok is True
    assert result.status == "OK"
    assert result.checks[-1].code == "FABRIC_SPARK_POOL_COMPATIBLE"
    assert result.checks[-1].details
    assert result.checks[-1].details["default_pool"]["name"] == "cf_small_single_node"


def test_workspace_preflight_resolves_configured_lakehouse() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                }
            ),
            _json_response(
                {
                    "value": [
                        {
                            "id": "lakehouse-1",
                            "displayName": "contractforge_lh",
                            "type": "Lakehouse",
                            "workspaceId": "workspace-1",
                        }
                    ]
                }
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {
            "parameters": {
                "fabric": {
                    "workspace_id": "workspace-1",
                    "lakehouse_name": "contractforge_lh",
                }
            }
        },
        client=client,
    )

    assert result.status == "OK"
    assert result.items["lakehouse"] and result.items["lakehouse"]["id"] == "lakehouse-1"
    assert result.checks[-1].code == "FABRIC_LAKEHOUSE_RESOLVED"


def test_workspace_preflight_resolves_configured_notebook_name() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                }
            ),
            _json_response(
                {
                    "value": [
                        {
                            "id": "notebook-1",
                            "displayName": "cf_workspace_bronze_orders",
                            "type": "Notebook",
                            "workspaceId": "workspace-1",
                        }
                    ]
                }
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {
            "parameters": {
                "fabric": {
                    "workspace_id": "workspace-1",
                    "notebook_name": "cf_workspace_bronze_orders",
                }
            }
        },
        client=client,
    )

    assert result.status == "OK"
    assert result.items["notebook"] and result.items["notebook"]["id"] == "notebook-1"
    assert result.checks[-1].code == "FABRIC_NOTEBOOK_RESOLVED"


def test_workspace_preflight_warns_when_notebook_has_active_jobs() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                }
            ),
            _json_response(
                {
                    "value": [
                        {
                            "id": "notebook-1",
                            "displayName": "cf_smoke",
                            "type": "Notebook",
                            "workspaceId": "workspace-1",
                        }
                    ]
                }
            ),
            _json_response(
                {
                    "value": [
                        {"id": "job-1", "itemId": "notebook-1", "status": "Running"},
                        {"id": "job-2", "itemId": "notebook-1", "status": "Completed"},
                    ]
                }
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {
            "parameters": {
                "fabric": {
                    "workspace_id": "workspace-1",
                    "notebook_name": "cf_smoke",
                }
            }
        },
        client=client,
        check_notebook_jobs=True,
    )

    assert result.ok is True
    assert result.status == "OK_WITH_WARNINGS"
    assert result.checks[-1].code == "FABRIC_NOTEBOOK_ACTIVE_JOBS"
    assert result.checks[-1].details
    assert result.checks[-1].details["active_job_count"] == 1
    assert transport.requests[-1].url.endswith("/workspaces/workspace-1/items/notebook-1/jobs/instances")


def test_workspace_preflight_accepts_terminal_notebook_job_history() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                }
            ),
            _json_response(
                {
                    "value": [
                        {
                            "id": "notebook-1",
                            "displayName": "cf_smoke",
                            "type": "Notebook",
                            "workspaceId": "workspace-1",
                        }
                    ]
                }
            ),
            _json_response(
                {
                    "value": [
                        {"id": "job-1", "itemId": "notebook-1", "status": "Completed"},
                        {"id": "job-2", "itemId": "notebook-1", "status": "Failed"},
                    ]
                }
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {
            "parameters": {
                "fabric": {
                    "workspace_id": "workspace-1",
                    "notebook_id": "notebook-1",
                }
            }
        },
        client=client,
        check_notebook_jobs=True,
    )

    assert result.status == "OK"
    assert result.checks[-1].code == "FABRIC_NOTEBOOK_NO_ACTIVE_JOBS"
    assert result.checks[-1].details
    assert result.checks[-1].details["job_count"] == 2


def test_workspace_preflight_warns_for_optional_missing_lakehouse() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                }
            ),
            _json_response({"value": []}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {
            "parameters": {
                "fabric": {
                    "workspace_id": "workspace-1",
                    "lakehouse_name": "missing_lh",
                }
            }
        },
        client=client,
    )

    assert result.ok is True
    assert result.status == "OK_WITH_WARNINGS"
    assert result.checks[-1].code == "FABRIC_LAKEHOUSE_NOT_FOUND"
    assert result.checks[-1].status == "WARNING"


def test_workspace_preflight_blocks_for_required_missing_lakehouse() -> None:
    transport = FakeTransport(
        [
            _json_response(
                {
                    "id": "workspace-1",
                    "displayName": "Manager",
                    "type": "Workspace",
                    "capacityId": "capacity-1",
                }
            ),
            _json_response({"value": []}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = check_fabric_workspace_preflight(
        {"parameters": {"fabric": {"workspace_id": "workspace-1"}}},
        client=client,
        require_lakehouse=True,
    )

    assert result.ok is False
    assert result.status == "BLOCKED"
    assert result.checks[-1].code == "FABRIC_LAKEHOUSE_NOT_FOUND"
