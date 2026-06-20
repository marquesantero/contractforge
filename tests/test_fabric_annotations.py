from __future__ import annotations

import json
from datetime import datetime

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import (
    annotation_steps,
    annotations_plan,
    has_annotations,
    render_annotations_evidence_sql,
    render_annotations_plan,
    render_fabric_contract,
)


def _raw_contract() -> dict[str, object]:
    return {
        "source": {"type": "table", "table": "workspace.bronze.orders"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "append",
        "annotations": {
            "table": {
                "description": "Clean order table",
                "aliases": ["orders_curated"],
                "tags": {"domain": "sales", "token": "secret-token"},
                "deprecated": {"since": "2026-01-01", "replacement": "orders_v2"},
            },
            "columns": {
                "customer_email": {
                    "description": "Customer email address",
                    "pii": {"enabled": True, "type": "email", "sensitivity": "confidential"},
                    "tags": {"business_name": "Customer email"},
                }
            },
        },
    }


def test_fabric_annotations_plan_renders_table_and_column_changes() -> None:
    contract = semantic_contract_from_mapping(_raw_contract())

    assert has_annotations(contract) is True
    steps = annotation_steps(contract)
    plan = annotations_plan(contract)

    assert plan["adapter"] == "fabric"
    assert plan["target"] == "silver.orders"
    assert plan["apply_mode"] == "review_only"
    assert any(step["annotation_type"] == "description" and step["annotation_scope"] == "table" for step in steps)
    assert any(step["key"] == "alias_1" and step["value"] == "orders_curated" for step in steps)
    assert any(step["key"] == "pii_type" and step["column_name"] == "customer_email" for step in steps)
    assert any(step["key"] == "token" and step["value"] == "***REDACTED***" for step in steps)


def test_fabric_annotations_plan_json_is_parseable() -> None:
    contract = semantic_contract_from_mapping(_raw_contract())

    payload = json.loads(render_annotations_plan(contract))

    assert payload["status"] == "PLANNED"
    assert payload["changes"]


def test_fabric_annotations_evidence_sql_targets_delta_control_table() -> None:
    contract = semantic_contract_from_mapping(_raw_contract())
    sql = render_annotations_evidence_sql(
        contract,
        schema="contractforge",
        run_id="run-1",
        captured_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert "INSERT INTO `contractforge`.`ctrl_ingestion_annotations`" in sql
    assert "'silver.orders'" in sql
    assert "'fabric_catalog_annotation_plan'" in sql
    assert "TIMESTAMP '2026-01-01 12:00:00'" in sql
    assert "DATE '2026-01-01'" in sql
    assert "'contractforge-fabric'" in sql


def test_fabric_render_contract_emits_annotations_artifact() -> None:
    artifacts = render_fabric_contract(_raw_contract()).artifacts
    payload = json.loads(artifacts["workspace_silver_orders.fabric.annotations.json"])

    assert payload["target"] == "silver.orders"
    assert payload["apply_mode"] == "review_only"


def test_fabric_notebook_records_annotation_review_evidence_at_runtime() -> None:
    notebook = render_fabric_contract(_raw_contract()).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "_CF_ANNOTATION_STEPS = json.loads(" in notebook
    assert "def _cf_record_annotations_evidence(status='VALIDATED'):" in notebook
    assert "'ctrl_ingestion_annotations'" in notebook
    assert "'applied_sql': 'fabric_catalog_annotation_plan'" in notebook
    assert "    _cf_record_annotations_evidence()" in notebook


def test_fabric_annotations_noop_without_metadata() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "workspace.bronze.orders"},
            "target": {"schema": "silver", "table": "orders"},
            "mode": "append",
        }
    )

    assert has_annotations(contract) is False
    assert render_annotations_plan(contract) == ""
    assert render_annotations_evidence_sql(contract) == "-- No annotation intent declared.\n"
