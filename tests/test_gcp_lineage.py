from datetime import datetime, timezone

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.lineage import build_openlineage_event, openlineage_namespace, render_openlineage_insert_sql
from contractforge_gcp.runtime import BigQueryJobEvidence


def _contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "raw.orders"},
            "target": {"catalog": "test-project", "schema": "silver", "table": "orders"},
            "mode": "upsert",
            "merge_keys": ["order_id"],
        }
    )


def test_openlineage_namespace_defaults_to_bigquery_project() -> None:
    assert openlineage_namespace(_contract(), environment=GCPEnvironment(project_id="fallback")) == "bigquery://test-project"


def test_build_openlineage_event_redacts_sensitive_metrics() -> None:
    event = build_openlineage_event(
        _contract(),
        run_id="run-1",
        source_name="raw.orders",
        status="SUCCESS",
        started_at_utc=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        finished_at_utc=datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc),
        rows_read=12,
        rows_written=10,
        operation_metrics={"password": "secret", "totalSlotMs": 30},
        environment=GCPEnvironment(project_id="test-project"),
    )

    assert event["eventType"] == "COMPLETE"
    assert event["run"]["facets"]["processing_engine"]["name"] == "bigquery"
    assert event["outputs"][0]["facets"]["dataQualityMetrics"]["rowCount"] == 10
    assert event["facets"]["contractforge"]["operationMetrics"]["password"] == "***REDACTED***"


def test_render_openlineage_insert_sql_targets_gcp_lineage_table() -> None:
    job = BigQueryJobEvidence(
        job_id="job-1",
        job_type="QUERY",
        state="DONE",
        started_at_ms=1767268800000,
        finished_at_ms=1767268860000,
        statement_type="MERGE",
        inserted_rows=1,
        updated_rows=2,
        total_slot_ms=30,
    )

    sql = render_openlineage_insert_sql(
        _contract(),
        environment=GCPEnvironment(project_id="test-project", evidence_dataset="contractforge_ops"),
        job=job,
    )

    assert "INSERT INTO `test-project.contractforge_ops.contractforge_lineage_evidence`" in sql
    assert "`event_json`" in sql
    assert '"eventType":"COMPLETE"' in sql
    assert '"name":"bigquery"' in sql
    assert "test-project.silver.orders" in sql
