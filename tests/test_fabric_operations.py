from __future__ import annotations

import json
from datetime import datetime

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import (
    has_operations_metadata,
    operations_payload,
    render_fabric_contract,
    render_operations_insert_sql,
    render_operations_json,
)


def _contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "workspace.bronze.orders"},
            "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
            "mode": "append",
            "operations": {
                "ownership": {
                    "business_owner": "sales-ops",
                    "technical_owner": "data-platform",
                    "support_group": "platform-oncall",
                },
                "operations": {
                    "criticality": "high",
                    "expected_frequency": "daily",
                    "freshness_sla_minutes": 180,
                    "alert_on_failure": True,
                    "alert_on_quality_fail": True,
                    "runbook_url": "https://wiki.example.com/runbooks/orders",
                    "owners": ["sales-ops", "data-platform"],
                    "groups": "platform-oncall",
                    "tags": {"domain": "sales", "token": "secret-token"},
                },
            },
        }
    )


def test_fabric_operations_payload_is_normalized_and_redacted() -> None:
    payload = operations_payload(_contract())

    assert payload["criticality"] == "high"
    assert payload["expected_frequency"] == "daily"
    assert payload["freshness_sla_minutes"] == 180
    assert payload["alert_on_failure"] is True
    assert payload["alert_on_quality_fail"] is True
    assert payload["ownership"]["business_owner"] == "sales-ops"
    assert payload["owners"] == ["sales-ops", "data-platform"]
    assert payload["groups"] == ["platform-oncall"]
    assert payload["tags"]["token"] == "***REDACTED***"


def test_fabric_operations_insert_sql_targets_delta_evidence_table() -> None:
    sql = render_operations_insert_sql(
        _contract(),
        schema="contractforge",
        run_id="run-1",
        status="SUCCESS",
        recorded_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert has_operations_metadata(_contract()) is True
    assert "INSERT INTO `contractforge`.`ctrl_ingestion_operations`" in sql
    assert "`run_id`, `target_table`, `criticality`" in sql
    assert "'silver.orders'" in sql
    assert "'high'" in sql
    assert "180" in sql
    assert "TRUE" in sql
    assert "TIMESTAMP '2026-01-01 12:00:00'" in sql
    assert "'contractforge-fabric'" in sql


def test_fabric_operations_json_artifact_is_emitted_when_configured() -> None:
    raw_contract = {
        "source": {"type": "table", "table": "workspace.bronze.orders"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "append",
        "operations": {
            "criticality": "medium",
            "expected_frequency": "daily",
            "owners": "sales-ops|data-platform",
            "tags": {"domain": "sales"},
        },
    }

    artifacts = render_fabric_contract(raw_contract).artifacts
    payload = json.loads(artifacts["workspace_silver_orders.fabric.operations.json"])

    assert payload["criticality"] == "medium"
    assert payload["owners"] == ["sales-ops", "data-platform"]


def test_fabric_notebook_records_operations_metadata_at_runtime() -> None:
    raw_contract = {
        "source": {"type": "table", "table": "workspace.bronze.orders"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "append",
        "operations": {
            "ownership": {"technical_owner": "data-platform"},
            "operations": {
                "criticality": "high",
                "expected_frequency": "daily",
                "owners": ["data-platform"],
                "tags": {"domain": "sales"},
            },
        },
    }
    notebook = render_fabric_contract(raw_contract).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "def _cf_record_operations_evidence(status='RECORDED'):" in notebook
    assert "'ctrl_ingestion_operations'" in notebook
    assert "'criticality': payload.get('criticality')" in notebook
    assert "'ownership_json': json.dumps(payload.get('ownership') or {}, sort_keys=True, separators=(',', ':'))" in notebook
    assert "    _cf_record_operations_evidence()" in notebook


def test_fabric_operations_json_is_public_api() -> None:
    payload = render_operations_json(_contract())

    assert '"criticality": "high"' in payload
    assert '"business_owner": "sales-ops"' in payload
