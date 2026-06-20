from datetime import datetime

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws.lineage import build_openlineage_event, openlineage_namespace, render_openlineage_insert_sql


def _contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "lake", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
        }
    )


def test_openlineage_namespace_defaults_to_glue_database() -> None:
    assert openlineage_namespace(_contract()) == "aws-glue://lake_silver"


def test_build_openlineage_event_redacts_sensitive_metrics() -> None:
    event = build_openlineage_event(
        _contract(),
        run_id="run-1",
        source_name="postgres.public.orders",
        status="SUCCESS",
        started_at_utc=datetime(2026, 1, 1, 12, 0, 0),
        finished_at_utc=datetime(2026, 1, 1, 12, 1, 0),
        rows_read=12,
        rows_written=10,
        iceberg_snapshot_after="123",
        operation_metrics={"password": "secret", "added-records": "10"},
    )

    assert event["eventType"] == "COMPLETE"
    assert event["outputs"][0]["facets"]["dataQualityMetrics"]["rowCount"] == 10
    assert event["facets"]["contractforge"]["icebergSnapshotAfter"] == "123"
    assert event["facets"]["contractforge"]["operationMetrics"]["password"] == "***REDACTED***"


def test_render_openlineage_insert_sql_targets_aws_lineage_table() -> None:
    sql = render_openlineage_insert_sql(
        _contract(),
        run_id="run-1",
        source_name="postgres.public.orders",
        status="FAILED",
        started_at_utc=datetime(2026, 1, 1, 12, 0, 0),
        finished_at_utc=datetime(2026, 1, 1, 12, 1, 0),
        database="ops",
    )

    assert "INSERT INTO glue_catalog.`ops`.`ctrl_ingestion_lineage`" in sql
    assert '"eventType":"FAIL"' in sql
    assert "aws-glue://lake_silver" in sql
