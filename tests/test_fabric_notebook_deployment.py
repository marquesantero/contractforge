from __future__ import annotations

import json

from contractforge_fabric.runtime import (
    FabricHttpRequest,
    FabricHttpResponse,
    FabricRestClient,
    classify_fabric_notebook_run_result,
    definition_fingerprint,
    deploy_fabric_notebook_contract,
    fabric_notebook_default_lakehouse_execution_data,
    run_fabric_notebook_from_environment,
)
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.rendering.definition import render_notebook_item_definition
from contractforge_fabric.rendering import render_fabric_git_notebook_source


class FakeTransport:
    def __init__(self, responses: list[FabricHttpResponse]) -> None:
        self.responses = responses
        self.requests: list[FabricHttpRequest] = []

    def __call__(self, request: FabricHttpRequest) -> FabricHttpResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("Unexpected Fabric request")
        return self.responses.pop(0)


def _json_response(status: int, payload: dict[str, object]) -> FabricHttpResponse:
    return FabricHttpResponse(
        status_code=status,
        headers={},
        body=json.dumps(payload).encode("utf-8"),
    )


def _contract() -> dict[str, object]:
    return {
        "source": {"type": "parquet", "path": "Files/orders"},
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "overwrite",
    }


def _environment() -> dict[str, object]:
    return {
        "parameters": {
            "fabric": {
                "workspace_id": "workspace-1",
                "lakehouse_id": "lakehouse-1",
            }
        }
    }


def test_render_fabric_git_notebook_source_adds_required_prologue() -> None:
    source = render_fabric_git_notebook_source("print('ok')\n")

    assert source.startswith("# Fabric notebook source\r\n")
    assert "# METADATA ********************" in source
    assert "# CELL ********************" in source
    assert "print('ok')" in source


def test_fabric_notebook_default_lakehouse_execution_data() -> None:
    payload = fabric_notebook_default_lakehouse_execution_data(
        workspace_id="workspace-1",
        lakehouse_id="lakehouse-1",
    )

    assert payload == {
        "compute": "Spark",
        "computeConfiguration": {
            "defaultLakehouse": {
                "referenceType": "ById",
                "itemId": "lakehouse-1",
                "workspaceId": "workspace-1",
            }
        },
    }


def test_classify_fabric_notebook_run_result_success() -> None:
    outcome = classify_fabric_notebook_run_result({"status": "Succeeded"})

    assert outcome.ok is True
    assert outcome.code == "FABRIC_NOTEBOOK_RUN_SUCCEEDED"


def test_classify_fabric_notebook_run_result_in_progress() -> None:
    outcome = classify_fabric_notebook_run_result({"status": "NotStarted"})

    assert outcome.ok is False
    assert outcome.status == "RUNNING"
    assert outcome.code == "FABRIC_NOTEBOOK_RUN_IN_PROGRESS"


def test_classify_fabric_notebook_run_result_capacity_throttle() -> None:
    outcome = classify_fabric_notebook_run_result(
        {
            "status": "Failed",
            "failureReason": {
                "message": "[TooManyRequestsForCapacity] HTTP Response code 430: Spark rate limit"
            },
        }
    )

    assert outcome.ok is False
    assert outcome.status == "BLOCKED"
    assert outcome.code == "FABRIC_SPARK_CAPACITY_THROTTLED"


def test_classify_fabric_notebook_run_result_generic_failure() -> None:
    outcome = classify_fabric_notebook_run_result(
        {
            "status": "Failed",
            "failureReason": {"message": "bad source"},
        }
    )

    assert outcome.ok is False
    assert outcome.status == "FAILED"
    assert outcome.code == "FABRIC_NOTEBOOK_RUN_FAILED"
    assert outcome.message == "bad source"


def test_run_fabric_notebook_from_environment_uses_default_lakehouse() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=202,
                headers={
                    "Location": "https://api.fabric.microsoft.com/v1/jobs/instances/job-1",
                    "Retry-After": "10",
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    operation = run_fabric_notebook_from_environment(
        {
            "parameters": {
                "fabric": {
                    "workspace_id": "workspace-1",
                    "lakehouse_id": "lakehouse-1",
                    "notebook_id": "notebook-1",
                }
            }
        },
        client=client,
    )

    assert operation.retry_after_seconds == 10
    body = json.loads((transport.requests[0].body or b"").decode("utf-8"))
    assert body["executionData"]["compute"] == "Spark"
    assert body["executionData"]["computeConfiguration"]["defaultLakehouse"]["itemId"] == "lakehouse-1"


def test_deploy_fabric_notebook_contract_creates_missing_notebook() -> None:
    transport = FakeTransport(
        [
            _json_response(200, {"value": []}),
            _json_response(201, {"id": "notebook-1", "displayName": "cf_workspace_bronze_orders"}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = deploy_fabric_notebook_contract(_contract(), _environment(), client=client)

    assert result.action == "created"
    assert result.notebook_id == "notebook-1"
    create_request = transport.requests[1]
    assert create_request.method == "POST"
    assert create_request.url.endswith("/workspaces/workspace-1/notebooks")
    body = json.loads((create_request.body or b"").decode("utf-8"))
    assert body["displayName"] == "cf_workspace_bronze_orders"
    assert body["definition"]["format"] == "fabricGitSource"


def test_deploy_fabric_notebook_contract_skips_existing_notebook_by_default() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {"value": [{"id": "notebook-1", "displayName": "cf_workspace_bronze_orders"}]},
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = deploy_fabric_notebook_contract(_contract(), _environment(), client=client)

    assert result.action == "exists"
    assert result.notebook_id == "notebook-1"
    assert len(transport.requests) == 1


def test_deploy_fabric_notebook_contract_updates_existing_when_requested() -> None:
    current_definition = _render_definition()
    transport = FakeTransport(
        [
            _json_response(
                200,
                {"value": [{"id": "notebook-1", "displayName": "cf_workspace_bronze_orders"}]},
            ),
            _json_response(200, {"definition": {"format": "fabricGitSource", "parts": []}}),
            _json_response(200, {"id": "notebook-1"}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = deploy_fabric_notebook_contract(
        _contract(),
        _environment(),
        client=client,
        update_existing=True,
    )

    assert result.action == "updated"
    assert result.notebook_id == "notebook-1"
    assert result.definition_hash == definition_fingerprint(current_definition)
    assert result.previous_definition_hash == definition_fingerprint({"format": "fabricGitSource", "parts": []})
    assert transport.requests[2].url.endswith(
        "/workspaces/workspace-1/notebooks/notebook-1/updateDefinition?updateMetadata=True"
    )


def test_deploy_fabric_notebook_contract_blocks_configured_id_update_by_default() -> None:
    environment = {
        "parameters": {
            "fabric": {
                "workspace_id": "workspace-1",
                "lakehouse_id": "lakehouse-1",
                "notebook_id": "notebook-1",
            }
        }
    }
    transport = FakeTransport([_json_response(200, {"definition": {"format": "fabricGitSource", "parts": []}})])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = deploy_fabric_notebook_contract(_contract(), environment, client=client)

    assert result.action == "update_blocked"
    assert result.notebook_id == "notebook-1"
    assert result.message == "Existing Fabric Notebook definition differs; pass update_existing=True to update it."
    assert result.definition_hash != result.previous_definition_hash
    assert len(transport.requests) == 1
    assert transport.requests[0].url.endswith(
        "/workspaces/workspace-1/notebooks/notebook-1/getDefinition?format=fabricGitSource"
    )


def test_deploy_fabric_notebook_contract_blocks_update_when_existing_definition_is_unreadable() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {"value": [{"id": "notebook-1", "displayName": "cf_workspace_bronze_orders"}]},
            ),
            _json_response(409, {"error": {"code": "Conflict", "message": "Definition export is unavailable"}}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = deploy_fabric_notebook_contract(
        _contract(),
        _environment(),
        client=client,
        update_existing=True,
    )

    assert result.action == "update_blocked"
    assert result.notebook_id == "notebook-1"
    assert result.previous_definition_hash is None
    assert result.message == "Existing Fabric Notebook definition could not be read; update was blocked."
    assert len(transport.requests) == 2


def test_deploy_fabric_notebook_contract_skips_unchanged_existing_definition() -> None:
    definition = _render_definition()
    transport = FakeTransport(
        [
            _json_response(
                200,
                {"value": [{"id": "notebook-1", "displayName": "cf_workspace_bronze_orders"}]},
            ),
            _json_response(200, {"definition": definition}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = deploy_fabric_notebook_contract(
        _contract(),
        _environment(),
        client=client,
        update_existing=True,
    )

    assert result.action == "unchanged"
    assert result.notebook_id == "notebook-1"
    assert result.definition_hash == result.previous_definition_hash
    assert len(transport.requests) == 2
    assert transport.requests[1].url.endswith(
        "/workspaces/workspace-1/notebooks/notebook-1/getDefinition?format=fabricGitSource"
    )


def test_deploy_fabric_notebook_contract_checks_configured_notebook_id_for_changes() -> None:
    definition = _render_definition()
    environment = {
        "parameters": {
            "fabric": {
                "workspace_id": "workspace-1",
                "lakehouse_id": "lakehouse-1",
                "notebook_id": "notebook-1",
            }
        }
    }
    transport = FakeTransport([_json_response(200, {"definition": definition})])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = deploy_fabric_notebook_contract(_contract(), environment, client=client, update_existing=True)

    assert result.action == "unchanged"
    assert result.notebook_id == "notebook-1"
    assert len(transport.requests) == 1


def test_fabric_rest_client_adds_workspace_role_assignment() -> None:
    transport = FakeTransport(
        [
            _json_response(
                200,
                {"id": "assignment-1", "principal": {"id": "group-1", "type": "Group"}, "role": "Viewer"},
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = client.add_workspace_role_assignment(principal_id="group-1", principal_type="Group", role="Viewer")

    assert result["id"] == "assignment-1"
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith("/workspaces/workspace-1/roleAssignments")
    body = json.loads((request.body or b"").decode("utf-8"))
    assert body == {"principal": {"id": "group-1", "type": "Group"}, "role": "Viewer"}


def test_fabric_rest_client_bulk_sets_item_labels() -> None:
    transport = FakeTransport([_json_response(200, {"status": "Succeeded"})])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = client.bulk_set_item_labels(
        items=[{"id": "notebook-1", "type": "Notebook"}],
        label_id="label-1",
        assignment_method="Standard",
    )

    assert result["status"] == "Succeeded"
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith("/admin/items/bulkSetLabels")
    body = json.loads((request.body or b"").decode("utf-8"))
    assert body["items"] == [{"id": "notebook-1", "type": "Notebook"}]
    assert body["labelId"] == "label-1"


def test_fabric_rest_client_creates_lists_and_deletes_onelake_data_access_role() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=201,
                headers={
                    "ETag": '"etag-1"',
                    "Location": "https://api.fabric.microsoft.com/v1/workspaces/workspace-1/items/lakehouse-1/dataAccessRoles/role-1",
                },
                body=b"{}",
            ),
            _json_response(200, {"value": [{"name": "role-1"}]}),
            FabricHttpResponse(status_code=200, headers={}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = client.create_or_update_onelake_data_access_role(
        item_id="lakehouse-1",
        role={
            "name": "role-1",
            "kind": "Policy",
            "decisionRules": [
                {
                    "effect": "Permit",
                    "permission": [{"attributeName": "Action", "attributeValueIncludedIn": ["Read"]}],
                }
            ],
        },
    )
    roles = client.list_onelake_data_access_roles(item_id="lakehouse-1")
    client.delete_onelake_data_access_role(item_id="lakehouse-1", role_name="role-1")

    assert result["etag"] == '"etag-1"'
    assert roles == [{"name": "role-1"}]
    assert transport.requests[0].method == "POST"
    assert transport.requests[0].url.endswith(
        "/workspaces/workspace-1/items/lakehouse-1/dataAccessRoles?preview=true&dataAccessRoleConflictPolicy=Overwrite"
    )
    assert transport.requests[1].url.endswith("/workspaces/workspace-1/items/lakehouse-1/dataAccessRoles")
    assert transport.requests[2].method == "DELETE"
    assert transport.requests[2].url.endswith(
        "/workspaces/workspace-1/items/lakehouse-1/dataAccessRoles/role-1?preview=true"
    )


def test_fabric_rest_client_lists_deployment_pipelines_and_stages() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=200,
                headers={},
                body=b'{"value":[{"id":"pipeline-1","displayName":"ContractForge"}]}',
            ),
            FabricHttpResponse(
                status_code=200,
                headers={},
                body=b'{"value":[{"id":"stage-1","displayName":"Development","workspaceId":"workspace-1"}]}',
            ),
            FabricHttpResponse(
                status_code=200,
                headers={},
                body=b'{"value":[{"itemId":"target-notebook-1","sourceItemId":"notebook-1","itemType":"Notebook"}]}',
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    pipelines = client.list_deployment_pipelines()
    stages = client.list_deployment_pipeline_stages(deployment_pipeline_id="pipeline-1")
    items = client.list_deployment_pipeline_stage_items(deployment_pipeline_id="pipeline-1", stage_id="stage-1")

    assert pipelines == [{"id": "pipeline-1", "displayName": "ContractForge"}]
    assert stages == [{"id": "stage-1", "displayName": "Development", "workspaceId": "workspace-1"}]
    assert items == [{"itemId": "target-notebook-1", "sourceItemId": "notebook-1", "itemType": "Notebook"}]
    assert transport.requests[0].url.endswith("/deploymentPipelines")
    assert transport.requests[1].url.endswith("/deploymentPipelines/pipeline-1/stages")
    assert transport.requests[2].url.endswith("/deploymentPipelines/pipeline-1/stages/stage-1/items")


def test_fabric_rest_client_creates_workspace() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=201,
                headers={},
                body=b'{"id":"workspace-2","displayName":"ContractForge Target","type":"Workspace"}',
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    workspace = client.create_workspace(
        display_name="ContractForge Target",
        capacity_id="capacity-1",
        description="Temporary target workspace",
    )

    assert workspace["id"] == "workspace-2"
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith("/workspaces")
    body = json.loads((request.body or b"").decode("utf-8"))
    assert body == {
        "displayName": "ContractForge Target",
        "capacityId": "capacity-1",
        "description": "Temporary target workspace",
    }


def test_fabric_rest_client_deletes_item() -> None:
    transport = FakeTransport([FabricHttpResponse(status_code=200, headers={}, body=b"{}")])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    client.delete_item(item_id="item-1")

    request = transport.requests[0]
    assert request.method == "DELETE"
    assert request.url.endswith("/workspaces/workspace-1/items/item-1?hardDelete=True")


def test_fabric_rest_client_creates_assigns_unassigns_and_deletes_deployment_pipeline() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=201,
                headers={},
                body=(
                    b'{"id":"pipeline-1","displayName":"ContractForge",'
                    b'"stages":[{"id":"stage-1","displayName":"Development"}]}'
                ),
            ),
            FabricHttpResponse(status_code=200, headers={}, body=b"{}"),
            FabricHttpResponse(status_code=200, headers={}, body=b"{}"),
            FabricHttpResponse(status_code=200, headers={}, body=b"{}"),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    pipeline = client.create_deployment_pipeline(
        display_name="ContractForge",
        description="ContractForge test pipeline",
        stages=[
            {"displayName": "Development", "description": "Development stage", "isPublic": False},
            {"displayName": "Test", "description": "Test stage", "isPublic": False},
        ],
    )
    client.assign_workspace_to_deployment_pipeline_stage(
        deployment_pipeline_id="pipeline-1",
        stage_id="stage-1",
        workspace_id="workspace-1",
    )
    client.unassign_workspace_from_deployment_pipeline_stage(
        deployment_pipeline_id="pipeline-1",
        stage_id="stage-1",
    )
    client.delete_deployment_pipeline(deployment_pipeline_id="pipeline-1")

    assert pipeline["id"] == "pipeline-1"
    assert transport.requests[0].method == "POST"
    assert transport.requests[0].url.endswith("/deploymentPipelines")
    create_body = json.loads((transport.requests[0].body or b"").decode("utf-8"))
    assert create_body["displayName"] == "ContractForge"
    assert create_body["stages"][0]["displayName"] == "Development"
    assert transport.requests[1].url.endswith("/deploymentPipelines/pipeline-1/stages/stage-1/assignWorkspace")
    assign_body = json.loads((transport.requests[1].body or b"").decode("utf-8"))
    assert assign_body == {"workspaceId": "workspace-1"}
    assert transport.requests[2].url.endswith("/deploymentPipelines/pipeline-1/stages/stage-1/unassignWorkspace")
    assert transport.requests[3].method == "DELETE"
    assert transport.requests[3].url.endswith("/deploymentPipelines/pipeline-1")


def test_fabric_rest_client_deploys_pipeline_stage_content() -> None:
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=202,
                headers={
                    "Location": "https://api.fabric.microsoft.com/v1/operations/deploy-1",
                    "x-ms-operation-id": "deploy-1",
                    "Retry-After": "30",
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    operation = client.deploy_pipeline_stage_content(
        deployment_pipeline_id="pipeline-1",
        source_stage_id="stage-dev",
        target_stage_id="stage-prod",
        items=[{"sourceItemId": "notebook-1", "itemType": "Notebook"}],
        note="ContractForge deploy",
    )

    assert operation.operation_id == "deploy-1"
    assert operation.retry_after_seconds == 30
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith("/deploymentPipelines/pipeline-1/deploy")
    body = json.loads((request.body or b"").decode("utf-8"))
    assert body["sourceStageId"] == "stage-dev"
    assert body["targetStageId"] == "stage-prod"
    assert body["items"] == [{"sourceItemId": "notebook-1", "itemType": "Notebook"}]


def test_fabric_rest_client_connects_workspace_git() -> None:
    transport = FakeTransport([_json_response(200, {})])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    client.connect_workspace_git(
        git_provider_details={
            "gitProviderType": "GitHub",
            "ownerName": "owner",
            "repositoryName": "repo",
            "branchName": "main",
        },
        git_credentials={"source": "ConfiguredConnection", "connectionId": "connection-1"},
    )

    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith("/workspaces/workspace-1/git/connect")
    body = json.loads((request.body or b"").decode("utf-8"))
    assert body["gitProviderDetails"]["repositoryName"] == "repo"
    assert body["myGitCredentials"]["connectionId"] == "connection-1"


def test_definition_fingerprint_ignores_part_order_and_default_format() -> None:
    left = {"format": "fabricGitSource", "parts": [{"path": "b"}, {"path": "a"}]}
    right = {"parts": [{"path": "a"}, {"path": "b"}]}

    assert definition_fingerprint(left) == definition_fingerprint(right)


def _render_definition() -> dict[str, object]:
    semantic = semantic_contract_from_mapping(_contract())
    env = FabricEnvironment.from_contract(_environment())
    payload = json.loads(render_notebook_item_definition(semantic, env))
    return payload["create_notebook_request"]["definition"]
