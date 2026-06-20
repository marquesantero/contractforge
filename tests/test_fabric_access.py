from __future__ import annotations

import json
from datetime import datetime

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import (
    access_plan,
    access_steps,
    apply_native_access_governance,
    has_access_intent,
    native_access_apply_steps,
    render_access_evidence_sql,
    render_access_plan,
    render_fabric_contract,
)
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


def _raw_contract() -> dict[str, object]:
    return {
        "source": {"type": "table", "table": "workspace.bronze.orders"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "append",
        "access": {
            "access_policy": {"mode": "apply", "on_drift": "warn", "revoke_unmanaged": False},
            "grants": [{"principal": "fabric-analysts", "privileges": ["select"]}],
            "row_filters": [
                {
                    "name": "region_filter",
                    "function": "security.fn_region_filter",
                    "columns": ["region"],
                    "applies_to": {"principals": ["regional-analysts"]},
                }
            ],
            "column_masks": {
                "customer_email": {
                    "function": "security.fn_mask_email",
                    "using_columns": ["customer_email", "region"],
                    "applies_to": {"principals": ["support-users"]},
                }
            },
        },
    }


def test_fabric_access_plan_preserves_governance_intent_without_claiming_apply() -> None:
    contract = semantic_contract_from_mapping(_raw_contract())

    assert has_access_intent(contract) is True
    steps = access_steps(contract)
    plan = access_plan(contract)

    assert plan["adapter"] == "fabric"
    assert plan["target"] == "silver.orders"
    assert plan["contract_mode"] == "apply"
    assert plan["apply_mode"] == "review_only"
    assert {step["access_type"] for step in steps} == {"grant", "row_filter", "column_mask"}
    assert any(step["principal"] == "fabric-analysts" and step["privilege"] == "SELECT" for step in steps)
    assert any(step["column_name"] == "region" and step["function_name"] == "security.fn_region_filter" for step in steps)
    assert any(step["column_name"] == "customer_email" and step["privilege"] == "COLUMN_MASK" for step in steps)


def test_fabric_access_plan_includes_native_apply_steps_when_explicit_ids_are_declared() -> None:
    raw = _raw_contract()
    raw["extensions"] = {
        "fabric": {
            "access_apply": {
                "workspace_role_assignments": [
                    {
                        "principal": {"id": "group-1", "type": "Group"},
                        "role": "Viewer",
                    }
                ],
                "sensitivity_labels": [
                    {
                        "label_id": "label-1",
                        "items": [{"id": "notebook-1", "type": "Notebook"}],
                    }
                ],
                "onelake_data_access_roles": [
                    {
                        "item_id": "lakehouse-1",
                        "name": "contractforge_read_region",
                        "decisionRules": [
                            {
                                "effect": "Permit",
                                "permission": [
                                    {"attributeName": "Path", "attributeValueIncludedIn": ["*"]},
                                    {"attributeName": "Action", "attributeValueIncludedIn": ["Read"]},
                                ],
                                "constraints": {
                                    "columns": [
                                        {
                                            "tablePath": "/Tables/orders",
                                            "columnNames": ["region", "amount"],
                                            "columnEffect": "Permit",
                                            "columnAction": ["Read"],
                                        }
                                    ],
                                    "rows": [
                                        {
                                            "tablePath": "Tables/orders",
                                            "value": "select * from orders where region = 'NE'",
                                        }
                                    ],
                                },
                            }
                        ],
                        "delete_after_validation": True,
                    }
                ],
            }
        }
    }
    contract = semantic_contract_from_mapping(raw)

    plan = access_plan(contract)
    native_steps = native_access_apply_steps(contract)

    assert plan["apply_mode"] == "hybrid"
    assert {step["action"] for step in native_steps} == {
        "apply_workspace_role_assignment",
        "apply_sensitivity_label",
        "apply_onelake_data_access_role",
    }
    assert native_steps[0]["surface"] == "Fabric Core workspace roleAssignments API"
    assert native_steps[2]["surface"] == "Fabric OneLake dataAccessRoles preview API"


def test_fabric_apply_native_access_governance_dry_run_never_calls_fabric() -> None:
    raw = _raw_contract()
    raw["extensions"] = {
        "fabric": {
            "access_apply": {
                "workspace_role_assignments": [
                    {"principal_id": "group-1", "principal_type": "Group", "role": "Viewer"}
                ]
            }
        }
    }
    contract = semantic_contract_from_mapping(raw)
    transport = FakeTransport([])
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    results = apply_native_access_governance(contract, client=client, dry_run=True)

    assert [result.status for result in results] == ["PLANNED"]
    assert transport.requests == []


def test_fabric_apply_native_access_governance_calls_workspace_and_label_apis() -> None:
    raw = _raw_contract()
    raw["extensions"] = {
        "fabric": {
            "access_apply": {
                "workspace_role_assignments": [
                    {"principal_id": "group-1", "principal_type": "Group", "role": "Viewer"}
                ],
                "sensitivity_labels": [
                    {"label_id": "label-1", "items": [{"id": "notebook-1", "type": "Notebook"}]}
                ],
                "onelake_data_access_roles": [
                    {
                        "item_id": "lakehouse-1",
                        "name": "contractforge_read_region",
                        "decisionRules": [
                            {
                                "effect": "Permit",
                                "permission": [
                                    {"attributeName": "Path", "attributeValueIncludedIn": ["*"]},
                                    {"attributeName": "Action", "attributeValueIncludedIn": ["Read"]},
                                ],
                            }
                        ],
                        "delete_after_validation": True,
                    }
                ],
            }
        }
    }
    contract = semantic_contract_from_mapping(raw)
    transport = FakeTransport(
        [
            FabricHttpResponse(
                status_code=200,
                headers={},
                body=b'{"id":"assignment-1","principal":{"id":"group-1","type":"Group"},"role":"Viewer"}',
            ),
            FabricHttpResponse(status_code=200, headers={}, body=b'{"status":"Succeeded"}'),
            FabricHttpResponse(status_code=201, headers={"ETag": '"etag-1"'}, body=b"{}"),
            FabricHttpResponse(
                status_code=200,
                headers={},
                body=b'{"value":[{"name":"contractforge_read_region"}]}',
            ),
            FabricHttpResponse(status_code=200, headers={}, body=b""),
        ]
    )
    client = FabricRestClient(workspace_id="workspace-1", access_token="token-1", transport=transport)

    results = apply_native_access_governance(contract, client=client, dry_run=False)

    assert [result.status for result in results] == ["SUCCEEDED", "SUCCEEDED", "SUCCEEDED"]
    assert transport.requests[0].url.endswith("/workspaces/workspace-1/roleAssignments")
    assert transport.requests[1].url.endswith("/admin/items/bulkSetLabels")
    assert transport.requests[2].url.endswith(
        "/workspaces/workspace-1/items/lakehouse-1/dataAccessRoles?preview=true&dataAccessRoleConflictPolicy=Overwrite"
    )
    assert transport.requests[3].url.endswith("/workspaces/workspace-1/items/lakehouse-1/dataAccessRoles")
    assert transport.requests[4].url.endswith(
        "/workspaces/workspace-1/items/lakehouse-1/dataAccessRoles/contractforge_read_region?preview=true"
    )


def test_fabric_access_plan_json_is_parseable() -> None:
    contract = semantic_contract_from_mapping(_raw_contract())

    payload = json.loads(render_access_plan(contract))

    assert payload["status"] == "PLANNED"
    assert payload["steps"]
    assert payload["steps"][0]["applied_sql"] == "fabric_access_review_plan"


def test_fabric_access_evidence_sql_uses_core_control_table_shape() -> None:
    contract = semantic_contract_from_mapping(_raw_contract())
    sql = render_access_evidence_sql(
        contract,
        schema="contractforge",
        run_id="run-1",
        captured_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert "INSERT INTO `contractforge`.`ctrl_ingestion_access`" in sql
    assert "`access_run_id`" in sql
    assert "'silver.orders'" in sql
    assert "'fabric-analysts'" in sql
    assert "'ROW_FILTER'" in sql
    assert "'COLUMN_MASK'" in sql
    assert "'fabric_access_review_plan'" in sql
    assert "TIMESTAMP '2026-01-01 12:00:00'" in sql
    assert "DATE '2026-01-01'" in sql
    assert "'contractforge-fabric'" in sql


def test_fabric_render_contract_emits_access_artifact() -> None:
    artifacts = render_fabric_contract(_raw_contract()).artifacts
    payload = json.loads(artifacts["workspace_silver_orders.fabric.access.json"])

    assert payload["target"] == "silver.orders"
    assert payload["apply_mode"] == "review_only"


def test_fabric_notebook_records_access_review_evidence_at_runtime() -> None:
    notebook = render_fabric_contract(_raw_contract()).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "_CF_ACCESS_STEPS = json.loads(" in notebook
    assert "def _cf_record_access_evidence(status='VALIDATED'):" in notebook
    assert "'ctrl_ingestion_access'" in notebook
    assert "'applied_sql': step.get('applied_sql')" in notebook
    assert "'payload_json': json.dumps(payload, sort_keys=True, separators=(',', ':'))" in notebook
    assert "    _cf_record_access_evidence()" in notebook


def test_fabric_access_noop_without_governance_intent() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "workspace.bronze.orders"},
            "target": {"schema": "silver", "table": "orders"},
            "mode": "append",
        }
    )

    assert has_access_intent(contract) is False
    assert render_access_plan(contract) == ""
    assert render_access_evidence_sql(contract) == "-- No access intent declared.\n"
