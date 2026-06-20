from datetime import datetime, timezone

from contractforge_databricks.evidence import (
    EvidenceWriter,
    render_access_log_insert_sqls,
    render_annotation_log_insert_sqls,
    render_operations_log_insert_sql,
)


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def test_render_annotation_log_insert_sqls() -> None:
    statements = render_annotation_log_insert_sqls(
        run_id="run-1",
        target_table="main.silver.orders",
        entries=[
            {
                "annotation_scope": "column",
                "annotation_type": "tag",
                "column_name": "email",
                "key": "pii",
                "value": "true",
                "status": "APPLIED",
                "sql": "ALTER TABLE main.silver.orders ALTER COLUMN email SET TAGS ('pii'='true')",
                "annotation_ts_utc": datetime(2026, 1, 1, 12, 0, 0),
                "annotation_date": "2026-01-01",
                "ctrl_schema_version": 1,
            }
        ],
    )

    assert len(statements) == 1
    sql = statements[0]
    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_annotations`" in sql
    assert "annotation_date" in sql
    assert "'email'" in sql
    assert "CAST('2026-01-01' AS DATE)" in sql


def test_render_annotation_log_insert_sqls_enriches_audit_fields() -> None:
    statements = render_annotation_log_insert_sqls(
        run_id="run-1",
        target_table="main.silver.orders",
        entries=[{"annotation_scope": "table", "annotation_type": "comment", "status": "APPLIED"}],
        clock=lambda: datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
    )

    sql = statements[0]

    assert "annotation_ts_utc" in sql
    assert "annotation_date" in sql
    assert "framework_version" in sql
    assert "ctrl_schema_version" in sql
    assert "CAST(NULL AS TIMESTAMP)" not in sql
    assert "CAST(NULL AS DATE)" not in sql
    assert "2026-02-03 04:05:06" in sql


def test_render_access_log_insert_sqls_redacts_error() -> None:
    statements = render_access_log_insert_sqls(
        run_id="run-1",
        target_table="main.silver.orders",
        entries=[
            {
                "access_type": "grant",
                "principal": "analysts",
                "privilege": "SELECT",
                "status": "FAILED",
                "error_message": "token=raw-token",
                "sql": "GRANT SELECT ON TABLE main.silver.orders TO `analysts`",
                "revoke_unmanaged": False,
                "access_ts_utc": "2026-01-01 12:00:00",
                "access_date": "2026-01-01",
                "ctrl_schema_version": 1,
            }
        ],
    )

    sql = statements[0]

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_access`" in sql
    assert "access_run_id" in sql
    assert "'grant'" in sql
    assert "raw-token" not in sql
    assert "***REDACTED***" in sql


def test_render_access_log_insert_sqls_enriches_audit_fields() -> None:
    statements = render_access_log_insert_sqls(
        run_id="run-1",
        target_table="main.silver.orders",
        entries=[{"access_type": "grant", "principal": "analysts", "privilege": "SELECT", "status": "APPLIED"}],
        clock=lambda: datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
    )

    sql = statements[0]

    assert "action" in sql
    assert "payload_json" in sql
    assert "applied_at_utc" in sql
    assert "framework_version" in sql
    assert "ctrl_schema_version" in sql
    assert "CAST(NULL AS TIMESTAMP)" not in sql
    assert "CAST(NULL AS DATE)" not in sql
    assert "2026-02-03 04:05:06" in sql


def test_render_operations_log_insert_sql() -> None:
    sql = render_operations_log_insert_sql(
        {
            "run_id": "run-1",
            "target": {"table": "main.silver.orders"},
            "criticality": "high",
            "expected_frequency": "daily",
            "freshness_sla_minutes": "60",
            "alert_on_failure": True,
            "alert_on_quality_fail": False,
            "ownership_json": {"business_owner": "finance"},
            "owners_json": ["data-eng"],
            "status": "RECORDED",
            "recorded_at_utc": "2026-01-01 12:00:00",
            "ctrl_schema_version": 1,
        }
    )

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_operations`" in sql
    assert "'high'" in sql
    assert "60" in sql
    assert "true" in sql
    assert '{"business_owner":"finance"}' in sql


def test_render_operations_log_insert_sql_enriches_audit_fields() -> None:
    sql = render_operations_log_insert_sql(
        {
            "run_id": "run-1",
            "target": {"table": "main.silver.orders"},
            "criticality": "high",
            "status": "RECORDED",
        },
        clock=lambda: datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
    )

    assert "recorded_at_utc" in sql
    assert "framework_version" in sql
    assert "ctrl_schema_version" in sql
    assert "CAST(NULL AS TIMESTAMP)" not in sql
    assert "2026-02-03 04:05:06" in sql


def test_evidence_writer_can_write_governance_logs() -> None:
    runner = FakeRunner()
    writer = EvidenceWriter(runner, clock=lambda: "2026-02-03 04:05:06")

    writer.write_annotation_log({"run_id": "run-1", "target_table": "t", "status": "APPLIED"})
    writer.write_access_log({"run_id": "run-1", "target_table": "t", "status": "APPLIED"})
    writer.write_operations_log({"run_id": "run-1", "target_table": "t", "status": "RECORDED"})

    assert len(runner.statements) == 3
    assert "ctrl_ingestion_annotations" in runner.statements[0]
    assert "ctrl_ingestion_access" in runner.statements[1]
    assert "ctrl_ingestion_operations" in runner.statements[2]
    assert "2026-02-03 04:05:06" in runner.statements[2]
