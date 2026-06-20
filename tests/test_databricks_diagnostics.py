from contractforge_databricks.diagnostics import (
    ExplainPlanRecord,
    render_create_explain_table_sql,
    render_explain_insert_sql,
)
from contractforge_databricks.security import redact_text, redact_value


def test_redact_text_removes_common_secret_patterns() -> None:
    raw = (
        "jdbc:postgresql://user:s3cr3t@host/db?password=topsecret "
        "Authorization=Bearer raw-token "
        "X-Amz-Credential=AKIAEXAMPLE X-Amz-Signature=aws-signature "
        "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----"
    )

    redacted = redact_text(raw)

    assert "s3cr3t" not in redacted
    assert "topsecret" not in redacted
    assert "raw-token" not in redacted
    assert "AKIAEXAMPLE" not in redacted
    assert "aws-signature" not in redacted
    assert "secret\n" not in redacted
    assert "***REDACTED***" in redacted


def test_redact_value_redacts_nested_sensitive_keys_and_strings() -> None:
    value = redact_value({"auth": {"secret_scope": "prod"}, "url": "jdbc:x://u:p@h/db?token=abc"})

    assert value["auth"]["secret_scope"] == "***REDACTED***"
    assert "abc" not in value["url"]


def test_render_create_explain_table_sql() -> None:
    sql = render_create_explain_table_sql(catalog="main", schema="ops")

    assert "CREATE TABLE IF NOT EXISTS `main`.`ops`.`ctrl_ingestion_explain`" in sql


def test_render_explain_insert_sql_redacts_and_truncates() -> None:
    record = ExplainPlanRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        source_name="postgres.public.orders",
        mode="scd1_upsert",
        explain_format="formatted",
        plan_text="password=topsecret " + ("x" * 20),
    )

    sql = render_explain_insert_sql(record, truncate_at=25)

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_explain`" in sql
    assert "topsecret" not in sql
    assert "***REDACTED***" in sql
