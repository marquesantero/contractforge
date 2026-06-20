from __future__ import annotations

import json
from types import SimpleNamespace

import yaml
import contractforge_fabric.smoke.project as fabric_project_module
from contractforge_fabric.runtime import (
    FabricHttpRequest,
    FabricHttpResponse,
    FabricRestClient,
    run_fabric_project_smoke,
    run_fabric_contract_smoke,
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


def _json_response(status: int, payload: dict[str, object], headers: dict[str, str] | None = None) -> FabricHttpResponse:
    return FabricHttpResponse(
        status_code=status,
        headers=headers or {},
        body=json.dumps(payload).encode("utf-8"),
    )


def _contract() -> dict[str, object]:
    return {
        "source": {"type": "sql", "query": "SELECT 1 AS id"},
        "target": {"schema": "default", "table": "cf_smoke_sql"},
        "mode": "overwrite",
    }


def _environment() -> dict[str, object]:
    return {
        "parameters": {
            "fabric": {
                "workspace_id": "workspace-1",
                "lakehouse_id": "lakehouse-1",
                "notebook_name": "cf_default_cf_smoke_sql",
            }
        }
    }


def _workspace() -> dict[str, object]:
    return {
        "id": "workspace-1",
        "displayName": "Manager",
        "type": "Workspace",
        "capacityId": "capacity-1",
    }


def _lakehouse() -> dict[str, object]:
    return {
        "id": "lakehouse-1",
        "displayName": "contractforge_lh",
        "type": "Lakehouse",
        "workspaceId": "workspace-1",
    }


def test_run_fabric_contract_smoke_blocks_when_preflight_blocks() -> None:
    transport = FakeTransport(
        [
            _json_response(200, {"id": "workspace-1", "type": "Personal"}),
            _json_response(200, {"value": []}),
            _json_response(200, {"value": []}),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = run_fabric_contract_smoke(_contract(), _environment(), client=client)

    assert result.ok is False
    assert result.status == "BLOCKED"
    assert result.deployment is None
    assert result.outcome is None


def test_run_fabric_contract_smoke_can_submit_without_waiting() -> None:
    transport = FakeTransport(
        [
            _json_response(200, _workspace()),
            _json_response(200, {"value": [_lakehouse()]}),
            _json_response(200, {"value": []}),
            _json_response(200, {"value": []}),
            _json_response(
                202,
                {},
                {
                    "Location": "https://api.fabric.microsoft.com/v1/operations/create-1",
                    "Retry-After": "1",
                },
            ),
            _json_response(200, {"status": "Succeeded"}),
            _json_response(
                200,
                {"value": [{"id": "notebook-1", "displayName": "cf_default_cf_smoke_sql", "type": "Notebook"}]},
            ),
            _json_response(
                202,
                {},
                {
                    "Location": (
                        "https://api.fabric.microsoft.com/v1/workspaces/workspace-1/items/notebook-1"
                        "/jobs/instances/job-1"
                    ),
                    "Retry-After": "60",
                },
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = run_fabric_contract_smoke(_contract(), _environment(), client=client, wait=False)

    assert result.status == "RUNNING"
    assert result.outcome and result.outcome.code == "FABRIC_NOTEBOOK_RUN_SUBMITTED"
    assert result.job_reference and result.job_reference.job_instance_id == "job-1"
    evidence = result.to_dict()
    assert evidence["status"] == "RUNNING"
    assert evidence["job_reference"]["job_instance_id"] == "job-1"
    assert evidence["deployment"]["operation"]["location"] == "https://api.fabric.microsoft.com/v1/operations/create-1"


def test_run_fabric_contract_smoke_waits_and_classifies_capacity_throttle() -> None:
    transport = FakeTransport(
        [
            _json_response(200, _workspace()),
            _json_response(200, {"value": [_lakehouse()]}),
            _json_response(
                200,
                {"value": [{"id": "notebook-1", "displayName": "cf_default_cf_smoke_sql", "type": "Notebook"}]},
            ),
            _json_response(
                200,
                {"value": [{"id": "notebook-1", "displayName": "cf_default_cf_smoke_sql", "type": "Notebook"}]},
            ),
            _json_response(
                200,
                {"definition": {"format": "fabricGitSource", "parts": []}},
            ),
            _json_response(
                200,
                {"id": "notebook-1"},
            ),
            _json_response(
                202,
                {},
                {
                    "Location": (
                        "https://api.fabric.microsoft.com/v1/workspaces/workspace-1/items/notebook-1"
                        "/jobs/instances/job-1"
                    ),
                    "Retry-After": "1",
                },
            ),
            _json_response(200, {"id": "job-1", "status": "NotStarted"}),
            _json_response(
                200,
                {
                    "id": "job-1",
                    "status": "Failed",
                    "failureReason": {
                        "message": "[TooManyRequestsForCapacity] HTTP Response code 430"
                    },
                },
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = run_fabric_contract_smoke(
        _contract(),
        _environment(),
        client=client,
        retry_after_seconds=0,
        max_attempts=3,
    )

    assert result.status == "BLOCKED"
    assert result.outcome and result.outcome.code == "FABRIC_SPARK_CAPACITY_THROTTLED"


def test_run_fabric_contract_smoke_does_not_execute_after_blocked_update() -> None:
    transport = FakeTransport(
        [
            _json_response(200, _workspace()),
            _json_response(200, {"value": [_lakehouse()]}),
            _json_response(
                200,
                {"value": [{"id": "notebook-1", "displayName": "cf_default_cf_smoke_sql", "type": "Notebook"}]},
            ),
            _json_response(
                200,
                {"value": [{"id": "notebook-1", "displayName": "cf_default_cf_smoke_sql", "type": "Notebook"}]},
            ),
            _json_response(
                409,
                {"error": {"code": "Conflict", "message": "Definition export is unavailable"}},
            ),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    result = run_fabric_contract_smoke(
        _contract(),
        _environment(),
        client=client,
        update_existing=True,
    )

    assert result.status == "BLOCKED"
    assert result.deployment and result.deployment.action == "update_blocked"
    assert result.run_operation is None
    assert result.job_reference is None
    assert not any("/jobs/execute/instances" in request.url for request in transport.requests)


def test_run_fabric_project_smoke_runs_project_execution_order(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project.yaml"
    environment_path = tmp_path / "fabric.env.yaml"
    bronze_path = tmp_path / "contracts" / "bronze.yaml"
    silver_path = tmp_path / "contracts" / "silver.yaml"
    bronze_path.parent.mkdir()
    bronze_path.write_text(
        yaml.safe_dump(
            {
                "source": {"type": "sql", "query": "SELECT 1 AS id"},
                "target": {"schema": "bronze", "table": "orders"},
            }
        ),
        encoding="utf-8",
    )
    silver_path.write_text(
        yaml.safe_dump(
            {
                "source": {"type": "sql", "query": "SELECT * FROM bronze.orders"},
                "target": {"schema": "silver", "table": "orders"},
            }
        ),
        encoding="utf-8",
    )
    environment_path.write_text(
        yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1", "lakehouse_id": "lakehouse-1"}}}),
        encoding="utf-8",
    )
    project_path.write_text(
        yaml.safe_dump(
            {
                "environments": {"fabric": "fabric.env.yaml"},
                "execution_order": [
                    {
                        "name": "bronze",
                        "layer": "bronze",
                        "depends_on": [],
                        "contracts": {"fabric": "contracts/bronze.yaml"},
                    },
                    {
                        "name": "silver",
                        "layer": "silver",
                        "depends_on": ["bronze"],
                        "contracts": {"fabric": "contracts/silver.yaml"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    seen: list[dict[str, object]] = []

    def fake_smoke(contract, environment, *, client, wait, max_attempts, retry_after_seconds):
        seen.append(
            {
                "contract": contract,
                "environment": environment,
                "client": client,
                "wait": wait,
                "max_attempts": max_attempts,
                "retry_after_seconds": retry_after_seconds,
            }
        )
        return SimpleNamespace(
            ok=True,
            status="SUCCEEDED",
            to_dict=lambda: {"status": "SUCCEEDED", "ok": True},
        )

    monkeypatch.setattr(fabric_project_module, "run_fabric_contract_smoke", fake_smoke)

    result = run_fabric_project_smoke(project_path, max_attempts=7, retry_after_seconds=0)

    assert result.ok is True
    assert result.status == "SUCCEEDED"
    assert [step.name for step in result.steps] == ["bronze", "silver"]
    assert result.steps[1].depends_on == ("bronze",)
    assert len(seen) == 2
    assert seen[0]["contract"]["target"]["schema"] == "bronze"
    assert seen[1]["contract"]["target"]["schema"] == "silver"
    assert seen[0]["environment"]["parameters"]["fabric"]["workspace_id"] == "workspace-1"
    assert seen[0]["wait"] is True
    assert seen[0]["max_attempts"] == 7
    assert seen[0]["retry_after_seconds"] == 0
    payload = result.to_dict()
    assert payload["steps"][0]["result"]["status"] == "SUCCEEDED"


def test_run_fabric_project_smoke_creates_declared_shortcuts_before_steps(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project.yaml"
    environment_path = tmp_path / "fabric.env.yaml"
    contract_path = tmp_path / "contracts" / "bronze.yaml"
    contract_path.parent.mkdir()
    contract_path.write_text(
        yaml.safe_dump(
            {
                "source": {"type": "csv", "path": "Files/source-expansion/external-shortcuts/orders/orders.csv"},
                "target": {"schema": "bronze", "table": "orders"},
            }
        ),
        encoding="utf-8",
    )
    environment_path.write_text(
        yaml.safe_dump(
            {
                "parameters": {
                    "fabric": {
                        "workspace_id": "workspace-1",
                        "lakehouse_id": "lakehouse-1",
                        "connections": {"azure_blob_shortcut_connection_id": "connection-1"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    project_path.write_text(
        yaml.safe_dump(
            {
                "environments": {"fabric": "fabric.env.yaml"},
                "fabric_setup": {
                    "shortcuts": [
                        {
                            "path": "Files/source-expansion/external-shortcuts",
                            "name": "orders",
                            "target": {
                                "azureBlobStorage": {
                                    "location": "https://account.blob.core.windows.net",
                                    "subpath": "/container/orders",
                                    "connectionId": "{{ parameter:fabric.connections.azure_blob_shortcut_connection_id }}",
                                }
                            },
                        }
                    ]
                },
                "execution_order": [
                    {
                        "name": "bronze",
                        "layer": "bronze",
                        "contracts": {"fabric": "contracts/bronze.yaml"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    transport = FakeTransport(
        [
            _json_response(
                201,
                {
                    "path": "Files/source-expansion/external-shortcuts",
                    "name": "orders",
                    "target": {"type": "AzureBlobStorage"},
                },
            )
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)
    seen: list[dict[str, object]] = []

    def fake_smoke(contract, environment, *, client, wait, max_attempts, retry_after_seconds):
        seen.append({"contract": contract, "client": client})
        return SimpleNamespace(
            ok=True,
            status="SUCCEEDED",
            to_dict=lambda: {"status": "SUCCEEDED", "ok": True},
        )

    monkeypatch.setattr(fabric_project_module, "run_fabric_contract_smoke", fake_smoke)

    result = run_fabric_project_smoke(project_path, client=client)

    assert result.status == "SUCCEEDED"
    assert result.setups[0].type == "shortcut"
    assert result.setups[0].details["target_type"] == "azureBlobStorage"
    assert seen[0]["client"] is client
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.endswith(
        "/workspaces/workspace-1/items/lakehouse-1/shortcuts?shortcutConflictPolicy=CreateOrOverwrite"
    )
    assert json.loads((request.body or b"").decode("utf-8")) == {
        "path": "Files/source-expansion/external-shortcuts",
        "name": "orders",
        "target": {
            "azureBlobStorage": {
                "location": "https://account.blob.core.windows.net",
                "subpath": "/container/orders",
                "connectionId": "connection-1",
            }
        },
    }
    assert result.to_dict()["setups"][0]["status"] == "SUCCEEDED"


def test_run_fabric_project_smoke_stops_after_blocked_step(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project.yaml"
    environment_path = tmp_path / "fabric.env.yaml"
    first_path = tmp_path / "first.yaml"
    second_path = tmp_path / "second.yaml"
    first_path.write_text(yaml.safe_dump({"source": {"type": "sql"}, "target": {"table": "first"}}), encoding="utf-8")
    second_path.write_text(yaml.safe_dump({"source": {"type": "sql"}, "target": {"table": "second"}}), encoding="utf-8")
    environment_path.write_text(
        yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1", "lakehouse_id": "lakehouse-1"}}}),
        encoding="utf-8",
    )
    project_path.write_text(
        yaml.safe_dump(
            {
                "environments": {"fabric": "fabric.env.yaml"},
                "execution_order": [
                    {"name": "first", "contracts": {"fabric": "first.yaml"}},
                    {"name": "second", "contracts": {"fabric": "second.yaml"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_smoke(contract, environment, **kwargs):
        calls.append(contract["target"]["table"])
        return SimpleNamespace(
            ok=False,
            status="BLOCKED",
            to_dict=lambda: {"status": "BLOCKED", "ok": False},
        )

    monkeypatch.setattr(fabric_project_module, "run_fabric_contract_smoke", fake_smoke)

    result = run_fabric_project_smoke(project_path)

    assert result.status == "BLOCKED"
    assert [step.name for step in result.steps] == ["first"]
    assert calls == ["first"]


def test_run_fabric_project_smoke_accepts_expected_failed_step(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project.yaml"
    environment_path = tmp_path / "fabric.env.yaml"
    failure_path = tmp_path / "quality_failure.yaml"
    next_path = tmp_path / "next.yaml"
    failure_path.write_text(
        yaml.safe_dump({"source": {"type": "sql"}, "target": {"table": "quality_failure"}}),
        encoding="utf-8",
    )
    next_path.write_text(yaml.safe_dump({"source": {"type": "sql"}, "target": {"table": "next"}}), encoding="utf-8")
    environment_path.write_text(
        yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1", "lakehouse_id": "lakehouse-1"}}}),
        encoding="utf-8",
    )
    project_path.write_text(
        yaml.safe_dump(
            {
                "environments": {"fabric": "fabric.env.yaml"},
                "execution_order": [
                    {
                        "name": "quality_failure",
                        "expected_result": "failed",
                        "contracts": {"fabric": "quality_failure.yaml"},
                    },
                    {"name": "next", "contracts": {"fabric": "next.yaml"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    statuses = ["FAILED", "SUCCEEDED"]

    def fake_smoke(contract, environment, **kwargs):
        status = statuses.pop(0)
        return SimpleNamespace(
            ok=status == "SUCCEEDED",
            status=status,
            to_dict=lambda: {"status": status, "ok": status == "SUCCEEDED"},
        )

    monkeypatch.setattr(fabric_project_module, "run_fabric_contract_smoke", fake_smoke)

    result = run_fabric_project_smoke(project_path)

    assert result.status == "SUCCEEDED"
    assert [step.expected_result for step in result.steps] == ["failed", "succeeded"]
    assert [step.ok for step in result.steps] == [True, True]
    assert result.to_dict()["steps"][0]["expected_result"] == "failed"
    assert result.to_dict()["start_at"] is None


def test_run_fabric_project_smoke_can_start_at_named_step(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project.yaml"
    environment_path = tmp_path / "fabric.env.yaml"
    first_path = tmp_path / "first.yaml"
    second_path = tmp_path / "second.yaml"
    first_path.write_text(yaml.safe_dump({"source": {"type": "sql"}, "target": {"table": "first"}}), encoding="utf-8")
    second_path.write_text(yaml.safe_dump({"source": {"type": "sql"}, "target": {"table": "second"}}), encoding="utf-8")
    environment_path.write_text(
        yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1", "lakehouse_id": "lakehouse-1"}}}),
        encoding="utf-8",
    )
    project_path.write_text(
        yaml.safe_dump(
            {
                "environments": {"fabric": "fabric.env.yaml"},
                "execution_order": [
                    {"name": "first", "contracts": {"fabric": "first.yaml"}},
                    {"name": "second", "contracts": {"fabric": "second.yaml"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_smoke(contract, environment, **kwargs):
        calls.append(contract["target"]["table"])
        return SimpleNamespace(
            ok=True,
            status="SUCCEEDED",
            to_dict=lambda: {"status": "SUCCEEDED", "ok": True},
        )

    monkeypatch.setattr(fabric_project_module, "run_fabric_contract_smoke", fake_smoke)

    result = run_fabric_project_smoke(project_path, start_at="second")

    assert result.status == "SUCCEEDED"
    assert result.start_at == "second"
    assert [step.name for step in result.steps] == ["second"]
    assert calls == ["second"]


def test_run_fabric_project_smoke_rejects_unknown_expected_result(tmp_path) -> None:
    project_path = tmp_path / "project.yaml"
    environment_path = tmp_path / "fabric.env.yaml"
    contract_path = tmp_path / "contract.yaml"
    contract_path.write_text(yaml.safe_dump({"source": {"type": "sql"}, "target": {"table": "orders"}}), encoding="utf-8")
    environment_path.write_text(
        yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1", "lakehouse_id": "lakehouse-1"}}}),
        encoding="utf-8",
    )
    project_path.write_text(
        yaml.safe_dump(
            {
                "environments": {"fabric": "fabric.env.yaml"},
                "execution_order": [
                    {
                        "name": "bad_expectation",
                        "expected_result": "maybe",
                        "contracts": {"fabric": "contract.yaml"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    try:
        run_fabric_project_smoke(project_path)
    except ValueError as exc:
        assert "expected_result must be one of" in str(exc)
    else:  # pragma: no cover - defensive assertion style
        raise AssertionError("Expected invalid expected_result to fail")
