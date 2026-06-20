from __future__ import annotations

import json

from contractforge_fabric.cli import main as fabric_cli_main
from contractforge_fabric.deployment import deploy_fabric_project, render_fabric_project_deployment_manifest
from contractforge_fabric.runtime import FabricHttpRequest, FabricHttpResponse, FabricRestClient


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
    return FabricHttpResponse(status_code=status, headers={}, body=json.dumps(payload).encode("utf-8"))


def _write_project(tmp_path) -> tuple[object, object]:
    project = tmp_path / "project.yaml"
    environment = tmp_path / "fabric.environment.yaml"
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    environment.write_text(
        """
parameters:
  fabric:
    workspace_id: workspace-1
    lakehouse_id: lakehouse-1
""".lstrip(),
        encoding="utf-8",
    )
    (contracts / "01_orders.ingestion.yaml").write_text(
        """
source:
  type: parquet
  path: Files/orders
target:
  catalog: workspace
  schema: bronze
  table: orders
mode: overwrite
""".lstrip(),
        encoding="utf-8",
    )
    project.write_text(
        """
name: fabric-deployment-smoke
environments:
  fabric: fabric.environment.yaml
deployment:
  fabric:
    strategy: notebook_definition
    deployment_pipeline:
      pipeline_id: pipeline-1
      source_stage_id: dev-stage
      target_stage_id: prod-stage
execution_order:
  - name: bronze_orders
    layer: bronze
    contracts:
      fabric: contracts/01_orders.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )
    return project, environment


def test_render_fabric_project_deployment_manifest_is_deterministic(tmp_path) -> None:
    project, _environment = _write_project(tmp_path)

    manifest = render_fabric_project_deployment_manifest(project)

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["dry_run"] is True
    assert manifest["strategy"] == "notebook_definition"
    assert manifest["deployment_pipeline"]["pipeline_id"] == "pipeline-1"
    assert manifest["steps"][0]["name"] == "bronze_orders"
    assert manifest["steps"][0]["notebook_name"] == "cf_fabric-deployment-smoke_bronze_orders"
    assert len(manifest["steps"][0]["definition_hash"]) == 64


def test_deploy_fabric_project_dry_run_exposes_manifest_artifact(tmp_path) -> None:
    project, _environment = _write_project(tmp_path)

    result = deploy_fabric_project(project, dry_run=True)

    assert result.ok is True
    assert result.deployment_id.startswith("dep_")
    assert len(result.deployment_records) == 1
    assert result.deployment_records[0]["deployment_id"] == result.deployment_id
    assert result.deployment_records[0]["deployment_status"] == "PLANNED"
    assert result.deployment_records[0]["contract_hash"]
    assert "deployment/fabric_project_deployment_manifest.json" in result.deployment_artifacts
    assert "deployment/fabric_deployment_ledger.sql" in result.deployment_artifacts
    artifact = json.loads(result.deployment_artifacts["deployment/fabric_project_deployment_manifest.json"])
    assert artifact["deployment_id"] == result.deployment_id
    assert artifact["deployment_records"][0]["deployment_hash"] == result.deployment_records[0]["deployment_hash"]
    assert artifact["steps"][0]["contract"].replace("\\", "/").endswith("contracts/01_orders.ingestion.yaml")
    ledger_sql = result.deployment_artifacts["deployment/fabric_deployment_ledger.sql"]
    assert "ctrl_deployment_versions" in ledger_sql
    assert "INSERT INTO" in ledger_sql
    assert result.deployment_records[0]["deployment_hash"] in ledger_sql


def test_deploy_fabric_project_creates_notebook_without_running(tmp_path) -> None:
    project, _environment = _write_project(tmp_path)
    transport = FakeTransport(
        [
            _json_response(200, {"value": []}),
            _json_response(201, {"id": "notebook-1", "displayName": "cf_fabric-deployment-smoke_bronze_orders"}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = deploy_fabric_project(project, client=client, dry_run=False)

    assert result.ok is True
    assert result.steps[0].deployment is not None
    assert result.steps[0].deployment.action == "created"
    assert transport.requests[0].url.endswith("/workspaces/workspace-1/items?recursive=true&type=Notebook")
    assert transport.requests[1].url.endswith("/workspaces/workspace-1/notebooks")
    assert all("/jobs/execute/instances" not in request.url for request in transport.requests)


def test_deploy_fabric_project_polls_async_notebook_create_and_resolves_id(tmp_path) -> None:
    project, _environment = _write_project(tmp_path)
    transport = FakeTransport(
        [
            _json_response(200, {"value": []}),
            FabricHttpResponse(
                status_code=202,
                headers={
                    "Location": "https://api.fabric.microsoft.com/v1/operations/create-1",
                    "x-ms-operation-id": "create-1",
                },
            ),
            _json_response(200, {"status": "Succeeded"}),
            _json_response(
                200,
                {
                    "value": [
                        {
                            "id": "notebook-1",
                            "displayName": "cf_fabric-deployment-smoke_bronze_orders",
                        }
                    ]
                },
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = deploy_fabric_project(project, client=client, dry_run=False)

    assert result.steps[0].deployment is not None
    assert result.steps[0].deployment.notebook_id == "notebook-1"
    assert transport.requests[2].url == "https://api.fabric.microsoft.com/v1/operations/create-1"
    assert transport.requests[3].url.endswith("/workspaces/workspace-1/items?recursive=true&type=Notebook")


def test_fabric_cli_deploy_project_dry_run_outputs_summary(tmp_path, capsys) -> None:
    project, _environment = _write_project(tmp_path)

    exit_code = fabric_cli_main(["deploy-project", str(project), "--dry-run", "--summary-only"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "SUCCEEDED"
    assert payload["steps"][0]["name"] == "bronze_orders"
