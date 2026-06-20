from contractforge_databricks.evidence import EVIDENCE_TABLE_COLUMNS, render_create_evidence_tables_sql


def test_render_create_evidence_tables_sql() -> None:
    sql = render_create_evidence_tables_sql(catalog="main", schema="ops")

    assert "CREATE SCHEMA IF NOT EXISTS `main`.`ops`;" in sql
    assert "CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_runs`" in sql
    assert "CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_lineage`" in sql
    assert "CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_explain`" in sql
    assert "CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_annotations`" in sql
    assert "CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_operations`" in sql
    assert "access_type STRING" in sql
    assert "revoke_unmanaged BOOLEAN" in sql
    assert "USING DELTA;" in sql
    assert "USING DELTA PARTITIONED BY (run_date);" in sql
    assert "USING DELTA PARTITIONED BY (error_date);" in sql
    assert "run_id STRING" in sql


def test_evidence_ddl_uses_full_contractforge_control_columns() -> None:
    sql = render_create_evidence_tables_sql(catalog="main", schema="ops")

    for column in (
        "run_ts_utc TIMESTAMP",
        "source_system STRING",
        "source_capabilities_json STRING",
        "write_engine_selected STRING",
        "rows_expired BIGINT",
        "idempotency_key STRING",
        "annotations_result_json STRING",
    ):
        assert column in sql

    assert "access_run_id STRING" in sql
    assert "annotation_date DATE" in sql
    assert "stream_run_id STRING" in sql
    assert "operation_metrics_json STRING" in sql
    assert "ctrl_schema_version BIGINT" in sql


def test_evidence_schema_catalog_keeps_legacy_and_core_insert_columns() -> None:
    assert "metrics_json STRING" in EVIDENCE_TABLE_COLUMNS["runs"]
    assert "operation_metrics_json STRING" in EVIDENCE_TABLE_COLUMNS["runs"]
    assert "source_system STRING" in EVIDENCE_TABLE_COLUMNS["runs"]
    assert "error_class STRING" in EVIDENCE_TABLE_COLUMNS["errors"]
    assert "error_type STRING" in EVIDENCE_TABLE_COLUMNS["errors"]
    assert "record_ref STRING" in EVIDENCE_TABLE_COLUMNS["quarantine"]
    assert "record_payload STRING" in EVIDENCE_TABLE_COLUMNS["quarantine"]
    assert "plan_text STRING" in EVIDENCE_TABLE_COLUMNS["explain"]
