# Databricks notebook source
from __future__ import annotations

import json

dbutils.widgets.text("source_schema", "cf_supabase_newcore_demo")
dbutils.widgets.text("expected_products", "100000")
dbutils.widgets.text("expected_movements", "1000500")

source_schema = dbutils.widgets.get("source_schema")
expected_products = int(dbutils.widgets.get("expected_products"))
expected_movements = int(dbutils.widgets.get("expected_movements"))

jdbc_url = dbutils.secrets.get("contractforge-secrets", "supabase-jdbc-url")
jdbc_user = dbutils.secrets.get("contractforge-secrets", "supabase-user")
jdbc_password = dbutils.secrets.get("contractforge-secrets", "supabase-password")
options = {
    "url": jdbc_url,
    "user": jdbc_user,
    "password": jdbc_password,
    "driver": "org.postgresql.Driver",
    "fetchsize": "10000",
}


def count_table(table_name: str) -> int:
    query = f"(SELECT COUNT(*) AS rows FROM {source_schema}.{table_name}) cf_count"
    return int(spark.read.format("jdbc").options(**options, dbtable=query).load().collect()[0]["rows"])


summary = {
    "schema": source_schema,
    "products": count_table("products"),
    "product_movements": count_table("product_movements"),
}

if summary["products"] < expected_products:
    raise AssertionError(f"products below expected scale: {summary['products']} < {expected_products}")
if summary["product_movements"] < expected_movements:
    raise AssertionError(
        f"product_movements below expected scale: {summary['product_movements']} < {expected_movements}"
    )

dbutils.notebook.exit(json.dumps(summary, sort_keys=True))
