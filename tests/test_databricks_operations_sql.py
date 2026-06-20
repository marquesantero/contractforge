from datetime import datetime

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.operations.sql import has_operations_metadata
from contractforge_databricks.operations import render_operations_insert_sql, render_operations_json


def test_render_operations_metadata_for_databricks_evidence() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd0_append",
            "operations": {
                "ownership": {
                    "business_owner": "sales-ops",
                    "technical_owner": "data-platform",
                    "support_group": "data-platform",
                },
                "operations": {
                    "criticality": "high",
                    "expected_frequency": "daily",
                    "freshness_sla_minutes": 180,
                    "alert_on_failure": True,
                    "runbook_url": "https://wiki.example.com/runbooks/orders",
                    "owners": ["sales-ops", "data-platform"],
                    "groups": "platform-oncall",
                    "tags": {"domain": "sales"},
                },
            },
        }
    )

    payload = render_operations_json(contract)
    sql = render_operations_insert_sql(
        contract,
        run_id="run-1",
        status="SUCCESS",
        recorded_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert '"criticality": "high"' in payload
    assert '"business_owner": "sales-ops"' in payload
    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_operations`" in sql
    assert "'main.silver.orders'" in sql
    assert "'high'" in sql
    assert "180" in sql
    assert "true" in sql
    assert '\'{"business_owner":"sales-ops"' in sql
    assert has_operations_metadata(contract)
