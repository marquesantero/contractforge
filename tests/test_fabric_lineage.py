from __future__ import annotations

import json
from datetime import datetime, timezone

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import build_openlineage_event, render_fabric_contract, render_openlineage_event_json
from contractforge_fabric.naming import source_display_name, target_table_name


def _contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "sql", "query": "SELECT 1 AS id", "name": "orders_sql"},
            "target": {"catalog": "workspace", "schema": "gold", "table": "orders_daily"},
            "layer": "gold",
            "mode": "overwrite",
        }
    )


def test_fabric_openlineage_event_uses_fabric_namespace_and_target() -> None:
    contract = _contract()
    started = datetime(2026, 6, 10, 20, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 6, 10, 20, 1, tzinfo=timezone.utc)

    event = build_openlineage_event(
        contract,
        run_id="run-1",
        status="SUCCESS",
        started_at_utc=started,
        finished_at_utc=finished,
        rows_read=30,
        rows_written=3,
        rows_quarantined=2,
        input_schema=(("id", "BIGINT"),),
        output_schema=(("id", "BIGINT"), ("count", "BIGINT")),
        operation_metrics={"token": "secret-token", "duration": 60},
        spark_version="3.5",
    )

    assert event["eventType"] == "COMPLETE"
    assert event["producer"] == "contractforge-fabric"
    assert event["job"]["namespace"] == "fabric://workspace"
    assert event["job"]["name"] == "gold.orders_daily.scd0_overwrite"
    assert event["inputs"][0]["name"] == "orders_sql"
    assert event["outputs"][0]["name"] == "gold.orders_daily"
    assert event["outputs"][0]["facets"]["dataQualityMetrics"]["rowCount"] == 3
    assert event["facets"]["contractforge"]["rowsRead"] == 30
    assert event["facets"]["contractforge"]["rowsQuarantined"] == 2
    assert event["facets"]["contractforge"]["operationMetrics"]["token"] == "***REDACTED***"
    assert event["run"]["facets"]["processing_engine"]["version"] == "3.5"


def test_fabric_openlineage_event_json_is_sorted_and_parseable() -> None:
    contract = _contract()
    started = datetime(2026, 6, 10, 20, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 6, 10, 20, 1, tzinfo=timezone.utc)

    payload = render_openlineage_event_json(
        contract,
        run_id="run-1",
        status="FAILED",
        started_at_utc=started,
        finished_at_utc=finished,
    )

    parsed = json.loads(payload)
    assert parsed["eventType"] == "FAIL"
    assert parsed["schemaURL"] == "https://openlineage.io/spec/1-0-5/OpenLineage.json"


def test_fabric_naming_helpers_match_notebook_target_shape() -> None:
    contract = _contract()

    assert target_table_name(contract) == "gold.orders_daily"
    assert source_display_name(contract) == "orders_sql"


def test_fabric_notebook_renders_runtime_lineage_evidence() -> None:
    notebook = render_fabric_contract(
        {
            "source": {"type": "sql", "query": "SELECT 1 AS id", "name": "orders_sql"},
            "target": {"catalog": "workspace", "schema": "gold", "table": "orders_daily"},
            "layer": "gold",
            "mode": "overwrite",
        }
    ).artifacts["workspace_gold_orders_daily.fabric.notebook.py"]

    compile(notebook, "workspace_gold_orders_daily.fabric.notebook.py", "exec")
    assert "_CF_LINEAGE_NAMESPACE = \"fabric://workspace\"" in notebook
    assert "_CF_LINEAGE_SOURCE_NAME = \"orders_sql\"" in notebook
    assert "_CF_LINEAGE_TARGET_NAME = \"gold.orders_daily\"" in notebook
    assert "'ctrl_ingestion_lineage'" in notebook
    assert "'dataQualityMetrics'" in notebook
