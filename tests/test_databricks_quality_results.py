from datetime import datetime

from contractforge_databricks.quality import (
    QualityRuleResult,
    quality_status,
    quarantinable_results,
    render_quality_results_insert_sql,
    render_quarantine_reference_insert_sql,
)


def test_quality_status_empty_means_not_configured() -> None:
    assert quality_status(()) == "NOT_CONFIGURED"


def test_quality_status_passed_warned_and_failed() -> None:
    assert quality_status((QualityRuleResult("id_not_null", "PASSED"),)) == "PASSED"
    assert quality_status((QualityRuleResult("freshness", "WARNED", failed_count=1, severity="warn"),)) == "WARNED"
    assert quality_status((QualityRuleResult("id_not_null", "FAILED", failed_count=2),)) == "FAILED"


def test_quarantinable_results_filters_failed_quarantine_rules() -> None:
    results = (
        QualityRuleResult("warn_rule", "WARNED", failed_count=1, severity="warn"),
        QualityRuleResult("abort_rule", "FAILED", failed_count=1, severity="abort"),
        QualityRuleResult("quarantine_rule", "FAILED", failed_count=1, severity="quarantine"),
    )

    assert [result.rule_name for result in quarantinable_results(results)] == ["quarantine_rule"]


def test_render_quality_results_insert_sql() -> None:
    sql = render_quality_results_insert_sql(
        run_id="run-1",
        target_table="main.silver.orders",
        results=(QualityRuleResult("id_not_null", "FAILED", failed_count=2, message="bad rows"),),
        checked_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_quality`" in sql
    assert "'id_not_null'" in sql
    assert '"failed_count":2' in sql


def test_render_quarantine_reference_insert_sql() -> None:
    sql = render_quarantine_reference_insert_sql(
        run_id="run-1",
        target_table="main.silver.orders",
        record_ref="s3://quarantine/orders/run-1/part-000.json",
        reason="id_not_null",
        quarantined_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_quarantine`" in sql
    assert "'s3://quarantine/orders/run-1/part-000.json'" in sql
