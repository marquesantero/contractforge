"""Databricks template catalog for split ContractForge contracts."""

from __future__ import annotations

from typing import Any

ContractTemplate = dict[str, Any]
TEMPLATE_META_KEY = "_template"


def _template(
    name: str,
    category: str,
    description: str,
    ingestion: dict[str, Any],
    *,
    annotations: dict[str, Any] | None = None,
    operations: dict[str, Any] | None = None,
    access: dict[str, Any] | None = None,
    priority: int = 50,
) -> ContractTemplate:
    result: ContractTemplate = {
        TEMPLATE_META_KEY: {
            "name": name,
            "category": category,
            "description": description,
            "recommendation_priority": priority,
        },
        "ingestion": ingestion,
    }
    if annotations:
        result["annotations"] = annotations
    if operations:
        result["operations"] = operations
    if access:
        result["access"] = access
    return result


def _target(schema: str, table: str) -> dict[str, str]:
    return {"catalog": "main", "schema": schema, "table": table}


def _ops(domain: str) -> dict[str, Any]:
    return {
        "owner": "data-platform",
        "domain": domain,
        "criticality": "medium",
        "expected_frequency": "daily",
        "runbook_url": f"https://wiki.example.com/runbooks/{domain}",
    }


def _ann(description: str) -> dict[str, Any]:
    return {"policy": "warn", "table": {"comment": description, "tags": {"contractforge": "databricks"}}}


def _access(group: str) -> dict[str, Any]:
    return {"access_policy": {"mode": "validate_only", "on_drift": "warn"}, "grants": [{"principal": group, "privileges": ["SELECT"]}]}


from contractforge_databricks.templates.catalog_parity import PARITY_CONTRACT_TEMPLATES  # noqa: E402
from contractforge_databricks.templates.enrichment import enrich_contractforge_parity  # noqa: E402


BUILTIN_CONTRACT_TEMPLATES: dict[str, ContractTemplate] = {
    **PARITY_CONTRACT_TEMPLATES,
    "bronze_rest_api_incremental": _template(
        "bronze_rest_api_incremental",
        "bronze",
        "REST API landing through reviewed native passthrough or bounded file fetch.",
        {
            "preset": "bronze_file_append",
            "source": {"type": "native_passthrough", "system": "rest_api", "object": "orders"},
            "target": _target("raw", "b_orders_api"),
        },
        annotations=_ann("Raw REST API order events."),
        operations=_ops("b_orders_api"),
    ),
    "bronze_http_file_csv_snapshot": _template(
        "bronze_http_file_csv_snapshot",
        "bronze",
        "HTTP CSV snapshot landing.",
        {"preset": "bronze_full_overwrite", "source": {"type": "http_csv", "url": "https://example.com/orders.csv"}, "target": _target("raw", "b_orders_http")},
        annotations=_ann("Raw HTTP CSV orders."),
        operations=_ops("b_orders_http"),
    ),
    "bronze_autoloader_json": _template(
        "bronze_autoloader_json",
        "bronze",
        "Portable incremental files rendered as Databricks Auto Loader.",
        {"preset": "bronze_autoloader_append", "source": {"type": "incremental_files", "format": "json", "path": "s3://bucket/landing/orders/"}, "target": _target("raw", "b_orders_json")},
        annotations=_ann("Raw incremental JSON orders."),
        operations=_ops("b_orders_json"),
    ),
    "bronze_autoloader_available_now_json": _template(
        "bronze_autoloader_available_now_json",
        "bronze",
        "Available-now incremental JSON ingestion.",
        {"preset": "bronze_autoloader_append", "source": {"type": "incremental_files", "format": "json", "trigger": "available_now", "path": "s3://bucket/landing/orders/"}, "target": _target("raw", "b_orders_available_now")},
        annotations=_ann("Available-now incremental JSON orders."),
        operations=_ops("b_orders_available_now"),
    ),
    "bronze_autoloader_governed_delta": _template(
        "bronze_autoloader_governed_delta",
        "bronze",
        "Governed Auto Loader landing with Delta optimization preview.",
        {"preset": ["bronze_autoloader_append", "delta_optimized_writes", "governance_uc_basic"], "source": {"type": "incremental_files", "format": "json", "path": "s3://bucket/landing/governed/"}, "target": _target("raw", "b_governed_delta")},
        annotations=_ann("Governed raw landing table."),
        operations=_ops("b_governed_delta"),
        access=_access("data-engineers"),
    ),
    "bronze_object_storage_nested_json_shape": _template(
        "bronze_object_storage_nested_json_shape",
        "bronze",
        "Object-storage nested JSON with shape intent.",
        {"preset": "bronze_file_append", "source": {"type": "json", "path": "s3://bucket/events/"}, "shape": {"parse_json": [{"column": "payload", "schema": "STRUCT<id: STRING>", "alias": "payload_obj"}]}, "target": _target("raw", "b_nested_events")},
        annotations=_ann("Nested JSON event landing."),
        operations=_ops("b_nested_events"),
    ),
    "bronze_object_storage_small_files": _template(
        "bronze_object_storage_small_files",
        "bronze",
        "Object-storage small files batch append.",
        {"preset": "bronze_file_append", "source": {"type": "parquet", "path": "s3://bucket/small-files/"}, "target": _target("raw", "b_small_files")},
        annotations=_ann("Small-file batch landing."),
        operations=_ops("b_small_files"),
    ),
    "silver_jdbc_scd1_upsert": _template(
        "silver_jdbc_scd1_upsert",
        "silver",
        "JDBC SCD1 current-state upsert.",
        {"preset": ["silver_incremental_watermark_upsert", "quality_quarantine", "delta_optimized_writes"], "source": {"type": "jdbc", "table": "public.orders"}, "target": _target("curated", "s_orders"), "merge_keys": ["order_id"], "watermark_columns": ["updated_at"]},
        annotations=_ann("Current-state orders from JDBC."),
        operations=_ops("s_orders"),
        access=_access("sales-analytics"),
    ),
    "silver_jdbc_rds_iam_hash_diff": _template(
        "silver_jdbc_rds_iam_hash_diff",
        "silver",
        "JDBC RDS IAM hash-diff append.",
        {"preset": ["silver_hash_diff_append", "quality_quarantine"], "source": {"type": "postgres", "table": "public.orders", "auth": {"type": "rds_iam"}}, "target": _target("curated", "s_orders_hash_diff"), "hash_keys": ["order_id"]},
        annotations=_ann("Hash-diff order changes from JDBC."),
        operations=_ops("s_orders_hash_diff"),
    ),
    "silver_lakeflow_auto_cdc_scd1_preview": _template(
        "silver_lakeflow_auto_cdc_scd1_preview",
        "silver",
        "Lakeflow AUTO CDC SCD1 review artifact with Delta fallback semantics.",
        {"preset": ["silver_scd1_upsert", "delta_liquid_clustering"], "source": {"type": "table", "table": "main.raw.customer_cdc"}, "target": _target("curated", "s_customers_current"), "merge_keys": ["customer_id"], "extensions": {"databricks": {"cluster_columns": ["customer_id"], "write_engine": {"requested": "lakeflow_auto_cdc", "fallback_policy": "preview_only"}}}},
        annotations=_ann("Current customers with Lakeflow review evidence."),
        operations=_ops("s_customers_current"),
    ),
    "silver_lakeflow_auto_cdc_scd2_preview": _template(
        "silver_lakeflow_auto_cdc_scd2_preview",
        "silver",
        "Lakeflow AUTO CDC SCD2 review artifact with Delta baseline.",
        {"preset": ["silver_scd2_historical", "delta_liquid_clustering"], "source": {"type": "table", "table": "main.raw.product_cdc"}, "target": _target("curated", "s_products_history"), "merge_keys": ["product_id"], "extensions": {"databricks": {"cluster_columns": ["product_id"], "write_engine": {"requested": "lakeflow_auto_cdc", "fallback_policy": "preview_only"}}}},
        annotations=_ann("Product SCD2 history with Lakeflow review evidence."),
        operations=_ops("s_products_history"),
    ),
    "silver_raw_json_payload_shape": _template(
        "silver_raw_json_payload_shape",
        "silver",
        "Raw JSON payload parsing into a curated table.",
        {"preset": "silver_scd1_upsert", "source": {"type": "table", "table": "main.raw.b_events"}, "shape": {"parse_json": [{"column": "payload", "schema": "STRUCT<event_id: STRING>", "alias": "payload_obj"}], "columns": {"payload_obj.event_id": {"alias": "event_id", "cast": "STRING"}}}, "target": _target("curated", "s_events"), "merge_keys": ["event_id"]},
        annotations=_ann("Curated event payloads."),
        operations=_ops("s_events"),
    ),
    "silver_parallel_arrays_shape": _template(
        "silver_parallel_arrays_shape",
        "silver",
        "Parallel array normalization review template.",
        {"preset": "silver_scd1_upsert", "source": {"type": "table", "table": "main.raw.b_forecast"}, "shape": {"zip_arrays": [{"alias": "hour", "columns": {"times": "time", "values": "value"}}], "arrays": [{"path": "hour", "mode": "explode_outer", "alias": "hour"}]}, "target": _target("curated", "s_hourly_forecast"), "merge_keys": ["forecast_id"]},
        annotations=_ann("Forecast rows derived from parallel arrays."),
        operations=_ops("s_hourly_forecast"),
    ),
    "silver_snapshot_soft_delete": _template(
        "silver_snapshot_soft_delete",
        "silver",
        "Current-state snapshot with soft delete for missing rows.",
        {"preset": "silver_snapshot_soft_delete", "source": {"type": "table", "table": "main.raw.b_devices_snapshot"}, "target": _target("curated", "s_devices"), "merge_keys": ["device_id"]},
        annotations=_ann("Device snapshot with soft delete semantics."),
        operations=_ops("s_devices"),
    ),
    "silver_scd2_history": _template(
        "silver_scd2_history",
        "silver",
        "SCD2 historical table.",
        {"preset": "silver_scd2_historical", "source": {"type": "table", "table": "main.raw.b_customers"}, "target": _target("curated", "s_customers_history"), "merge_keys": ["customer_id"]},
        annotations=_ann("Customer SCD2 history."),
        operations=_ops("s_customers_history"),
    ),
    "gold_full_refresh_kpi": _template(
        "gold_full_refresh_kpi",
        "gold",
        "Gold KPI table recalculated by full refresh.",
        {"preset": "gold_full_refresh", "source": {"type": "sql", "query": "SELECT order_date, count(*) AS orders FROM main.curated.s_orders GROUP BY order_date"}, "target": _target("analytics", "g_daily_orders")},
        annotations=_ann("Daily order KPI table."),
        operations=_ops("g_daily_orders"),
        access=_access("executive-dashboards"),
    ),
}

enrich_contractforge_parity(BUILTIN_CONTRACT_TEMPLATES)
