from datetime import datetime

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.lineage import build_openlineage_event, openlineage_namespace, render_openlineage_insert_sql


def _contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
        }
    )


def test_openlineage_namespace_defaults_to_databricks_catalog() -> None:
    assert openlineage_namespace(_contract()) == "databricks://main"


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
        input_schema=(("id", "bigint"),),
        output_schema=(("id", "bigint"), ("amount", "double")),
        operation_metrics={"password": "secret", "numTargetRowsInserted": "10"},
    )

    assert event["eventType"] == "COMPLETE"
    assert event["outputs"][0]["facets"]["dataQualityMetrics"]["rowCount"] == 10
    assert event["facets"]["contractforge"]["operationMetrics"]["password"] == "***REDACTED***"


def test_build_openlineage_event_includes_parent_facet() -> None:
    event = build_openlineage_event(
        _contract(),
        run_id="child-1",
        source_name="postgres.public.orders",
        status="SUCCESS",
        started_at_utc=datetime(2026, 1, 1, 12, 0, 0),
        finished_at_utc=datetime(2026, 1, 1, 12, 1, 0),
        parent_run_id="parent-1",
        source_code_url="jobs/orders_ingest",
    )

    assert event["run"]["facets"]["parent"]["run"]["runId"] == "parent-1"
    assert event["run"]["facets"]["parent"]["job"]["name"] == "jobs/orders_ingest"


def test_build_openlineage_event_includes_runtime_facets_when_available() -> None:
    event = build_openlineage_event(
        _contract(),
        run_id="run-1",
        source_name="postgres.public.orders",
        status="SUCCESS",
        started_at_utc=datetime(2026, 1, 1, 12, 0, 0),
        finished_at_utc=datetime(2026, 1, 1, 12, 1, 0),
        spark_version="16.4",
        source_code_url="jobs/orders_ingest",
    )

    assert event["run"]["facets"]["processing_engine"]["version"] == "16.4"
    assert event["job"]["facets"]["sourceCodeLocation"]["url"] == "jobs/orders_ingest"


def test_render_openlineage_insert_sql() -> None:
    sql = render_openlineage_insert_sql(
        _contract(),
        run_id="run-1",
        source_name="postgres.public.orders",
        status="FAILED",
        started_at_utc=datetime(2026, 1, 1, 12, 0, 0),
        finished_at_utc=datetime(2026, 1, 1, 12, 1, 0),
    )

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_lineage`" in sql
    assert '"eventType":"FAIL"' in sql
