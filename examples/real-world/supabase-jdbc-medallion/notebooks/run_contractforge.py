# Databricks notebook source
from __future__ import annotations

import json
from pathlib import Path

from contractforge_databricks import DatabricksIngestOptions, ingest_databricks_bundle


class SparkSqlRunner:
    def __init__(self, spark_session):
        self._spark = spark_session

    def sql(self, statement: str):
        return self._spark.sql(statement)


dbutils.widgets.text("bundle_root", "/Workspace/Shared/contractforge-examples/Supabase_JDBC_Medallion")
dbutils.widgets.text("contract", "")
dbutils.widgets.text("evidence_catalog", "workspace")
dbutils.widgets.text("evidence_schema", "cf_supabase_jdbc_e2e_v2_ops")

bundle_root = dbutils.widgets.get("bundle_root").rstrip("/")
contract = dbutils.widgets.get("contract").strip()
if not contract:
    raise ValueError("contract widget is required")

path = Path(f"{bundle_root}/{contract}")
result = ingest_databricks_bundle(
    path,
    spark=spark,
    runner=SparkSqlRunner(spark),
    options=DatabricksIngestOptions(
        catalog=dbutils.widgets.get("evidence_catalog"),
        schema=dbutils.widgets.get("evidence_schema"),
        runtime_metadata={"runtime_type": "serverless", "deployment": "databricks_asset_bundle"},
    ),
    collect_metrics=True,
)

dbutils.notebook.exit(json.dumps(result, default=str, sort_keys=True))
