# Databricks notebook source
from __future__ import annotations

import json

dbutils.widgets.text("evidence_catalog", "workspace")
dbutils.widgets.text("evidence_schema", "cf_supabase_jdbc_e2e_v2_ops")
dbutils.widgets.text("target_catalog", "workspace")
dbutils.widgets.text("project_prefix", "cf_supabase_jdbc_e2e_v2")

evidence_catalog = dbutils.widgets.get("evidence_catalog")
evidence_schema = dbutils.widgets.get("evidence_schema")
target_catalog = dbutils.widgets.get("target_catalog")
project_prefix = dbutils.widgets.get("project_prefix")

targets = {
    "bronze_products": f"{target_catalog}.{project_prefix}_bronze.b_products_jdbc",
    "bronze_movements": f"{target_catalog}.{project_prefix}_bronze.b_product_movements_jdbc",
    "silver_product_tags": f"{target_catalog}.{project_prefix}_silver.s_product_tags",
    "silver_movements_current": f"{target_catalog}.{project_prefix}_silver.s_movements_current",
    "gold_brand_inventory": f"{target_catalog}.{project_prefix}_gold.g_brand_inventory",
}
controls = {
    "runs": f"{evidence_catalog}.{evidence_schema}.ctrl_ingestion_runs",
    "quality": f"{evidence_catalog}.{evidence_schema}.ctrl_ingestion_quality",
    "errors": f"{evidence_catalog}.{evidence_schema}.ctrl_ingestion_errors",
    "state": f"{evidence_catalog}.{evidence_schema}.ctrl_ingestion_state",
    "metadata": f"{evidence_catalog}.{evidence_schema}.ctrl_ingestion_metadata",
}

summary = {"targets": {}, "controls": {}, "latest_runs": {}}
for name, table in targets.items():
    summary["targets"][name] = spark.table(table).count()
for name, table in controls.items():
    summary["controls"][name] = spark.table(table).count()

target_sql_values = ", ".join("'" + table.replace("'", "''") + "'" for table in targets.values())
latest_runs = spark.sql(
    f"""
    SELECT run_id, target_table, status, quality_status, rows_read, rows_written, rows_quarantined, write_committed
    FROM (
      SELECT *,
             row_number() OVER (PARTITION BY target_table ORDER BY started_at_utc DESC) AS rn
      FROM {controls["runs"]}
      WHERE target_table IN ({target_sql_values})
    )
    WHERE rn = 1
    """
).collect()
latest_runs_by_table = {row["target_table"]: row.asDict() for row in latest_runs}

expected_run_metrics = {
    "bronze_products": {"rows_read": 100000, "rows_written": 99900, "rows_quarantined": 100, "quality_status": "QUARANTINED"},
    "bronze_movements": {"rows_read": 1000000, "rows_written": 999950, "rows_quarantined": 50, "quality_status": "QUARANTINED"},
    "silver_product_tags": {"rows_read": 299700, "rows_written": 299700, "rows_quarantined": 0, "quality_status": "PASSED"},
    "silver_movements_current": {"rows_read": 999950, "rows_written": 999950, "rows_quarantined": 0, "quality_status": "PASSED"},
    "gold_brand_inventory": {"rows_read": 84, "rows_written": 84, "rows_quarantined": 0, "quality_status": "PASSED"},
}
for name, expected in expected_run_metrics.items():
    table = targets[name]
    latest = latest_runs_by_table.get(table)
    if latest is None:
        raise AssertionError(f"{name} has no latest run evidence in {controls['runs']}")
    summary["latest_runs"][name] = latest
    if latest["status"] != "SUCCESS":
        raise AssertionError(f"{name} expected latest run status SUCCESS, got {latest['status']}")
    if latest["write_committed"] is not True:
        raise AssertionError(f"{name} latest run was not committed")
    for field, expected_value in expected.items():
        actual_value = latest[field]
        if actual_value != expected_value:
            raise AssertionError(f"{name} latest run {field} expected {expected_value}, got {actual_value}")

preserving_write_targets = {"bronze_products", "bronze_movements"}
for name, expected in expected_run_metrics.items():
    actual_count = summary["targets"][name]
    rows_written = expected["rows_written"]
    rows_read = expected["rows_read"]
    if name in preserving_write_targets:
        if actual_count < rows_written or actual_count > rows_read:
            raise AssertionError(
                f"{name} target count must stay between latest rows_written and rows_read "
                f"for current-state preservation semantics; got {actual_count}"
            )
    elif actual_count != rows_written:
        raise AssertionError(f"{name} expected {rows_written} rows, got {actual_count}")

if summary["controls"]["runs"] < 5:
    raise AssertionError("expected at least five ingestion run records")
latest_run_ids = ", ".join("'" + row["run_id"].replace("'", "''") + "'" for row in summary["latest_runs"].values())
latest_error_count = spark.sql(
    f"SELECT count(*) AS errors FROM {controls['errors']} WHERE run_id IN ({latest_run_ids})"
).collect()[0]["errors"]
summary["controls"]["latest_errors"] = latest_error_count
if latest_error_count != 0:
    raise AssertionError(f"expected zero latest-run control errors, got {latest_error_count}")

dbutils.notebook.exit(json.dumps(summary, sort_keys=True))
