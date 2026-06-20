"""Parity enrichments for Databricks contract templates."""

from __future__ import annotations

from typing import Any

ContractTemplate = dict[str, Any]


def enrich_contractforge_parity(templates: dict[str, ContractTemplate]) -> None:
    """Restore mature original-template parameters using core canonical names."""
    _bronze_rest_api_incremental(templates)
    _bronze_http_file_csv_snapshot(templates)
    _bronze_autoloader_governed_delta(templates)
    _silver_jdbc_scd1_upsert(templates)
    _silver_jdbc_rds_iam_hash_diff(templates)
    _silver_scd2_history(templates)
    _silver_snapshot_soft_delete(templates)


def _bronze_rest_api_incremental(templates: dict[str, ContractTemplate]) -> None:
    ingestion = templates["bronze_rest_api_incremental"]["ingestion"]
    ingestion.update(
        {
            "source": {
                "type": "rest_api",
                "name": "orders_api",
                "request": {"url": "https://api.example.com/orders", "params": {"status": "open"}},
                "auth": {"type": "bearer_token", "token": "{{ secret:orders_api/token }}"},
                "pagination": {"type": "cursor", "cursor_param": "cursor", "next_cursor_path": "$.next"},
                "response": {"records_path": "$.data"},
                "incremental": {
                    "watermark_param": "updated_after",
                    "watermark_header": "X-Watermark",
                    "initial_value": "1970-01-01T00:00:00Z",
                },
                "limits": {"max_pages": 100, "timeout_seconds": 60, "retry_attempts": 3},
            },
            "mode": "scd0_append",
            "watermark_columns": ["updated_at"],
            "schema_policy": "additive_only",
            "quality_rules": {
                "not_null": ["id"],
                "expressions": [
                    {
                        "name": "valid_updated_at",
                        "expression": "updated_at IS NOT NULL",
                        "severity": "warn",
                        "message": "updated_at is missing from the API payload.",
                    }
                ],
            },
        }
    )


def _bronze_http_file_csv_snapshot(templates: dict[str, ContractTemplate]) -> None:
    ingestion = templates["bronze_http_file_csv_snapshot"]["ingestion"]
    ingestion.update(
        {
            "source": {
                "type": "http_csv",
                "url": "https://example.com/public/orders.csv",
                "format": "csv",
                "options": {"header": True, "multiLine": False},
                "read": {
                    "source_complete": True,
                    "schema": "order_id STRING, order_date DATE, customer_id STRING, amount DOUBLE, updated_at TIMESTAMP",
                    "timeout_seconds": 120,
                },
            },
            "schema_policy": "additive_only",
            "quality_rules": {
                "not_null": ["order_id"],
                "expressions": [
                    {
                        "name": "valid_amount",
                        "expression": "amount IS NULL OR amount >= 0",
                        "severity": "warn",
                        "message": "Negative amount in HTTP CSV.",
                    }
                ],
            },
        }
    )


def _bronze_autoloader_governed_delta(templates: dict[str, ContractTemplate]) -> None:
    ingestion = templates["bronze_autoloader_governed_delta"]["ingestion"]
    ingestion.update(
        {
            "preset": [
                "bronze_autoloader_append",
                "runtime_databricks_serverless",
                "delta_cdf_enabled",
                "delta_liquid_clustering",
                "write_engine_native_auto_preview",
                "governance_uc_basic",
            ],
            "source": {
                "type": "incremental_files",
                "format": "json",
                "path": "/Volumes/main/landing/orders_json",
                "progress_location": "/Volumes/main/ops/checkpoints/orders_json",
                "schema_tracking_location": "/Volumes/main/ops/autoloader_schemas/orders_json",
                "read": {"max_files_per_trigger": 50, "include_existing_files": True},
                "schema_hints": "order_id STRING, event_time TIMESTAMP, customer_id STRING",
                "trigger": "available_now",
            },
            "extensions": {"databricks": {"cluster_columns": ["order_id"]}},
            "idempotency_key": "b_orders_events_available_now",
        }
    )
    templates["bronze_autoloader_governed_delta"]["access"]["grants"] = [
        {"principal": "data-engineering", "privileges": ["SELECT", "MODIFY"]},
        {"principal": "sales-analytics", "privileges": ["SELECT"]},
    ]


def _silver_jdbc_scd1_upsert(templates: dict[str, ContractTemplate]) -> None:
    ingestion = templates["silver_jdbc_scd1_upsert"]["ingestion"]
    ingestion.update(
        {
            "source": {
                "type": "postgres",
                "url": "{{ secret:erp/postgres_url }}",
                "table": "public.orders",
                "auth": {"type": "basic", "username": "{{ secret:erp/user }}", "password": "{{ secret:erp/password }}"},
                "incremental": {"watermark_column": "updated_at", "initial_value": "1970-01-01 00:00:00"},
                "read": {"fetchsize": 10000, "partition_column": "id", "lower_bound": 1, "upper_bound": 10000000, "num_partitions": 16},
            },
            "transform": {"deduplicate": {"keys": ["order_id"], "order_by": "updated_at DESC NULLS LAST"}},
            "column_mapping": {"id": "order_id"},
            "quality_rules": {
                "not_null": ["order_id", "updated_at"],
                "unique_key": ["order_id"],
                "expressions": [{"name": "positive_amount", "expression": "amount >= 0", "severity": "quarantine", "message": "Negative amount."}],
            },
        }
    )


def _silver_jdbc_rds_iam_hash_diff(templates: dict[str, ContractTemplate]) -> None:
    ingestion = templates["silver_jdbc_rds_iam_hash_diff"]["ingestion"]
    source = dict(ingestion.get("source") or {})
    source.update(
        {
            "type": "postgres",
            "url": "jdbc:postgresql://orders.cluster-abcdefghijkl.us-east-1.rds.amazonaws.com:5432/erp",
            "table": "public.orders",
            "auth": {"type": "rds_iam", "username": "contractforge_app", "region": "us-east-1"},
        }
    )
    ingestion["source"] = source


def _silver_scd2_history(templates: dict[str, ContractTemplate]) -> None:
    ingestion = templates["silver_scd2_history"]["ingestion"]
    ingestion.update(
        {
            "transform": {"deduplicate": {"keys": ["customer_id"], "order_by": "updated_at DESC NULLS LAST"}},
            "hash_exclude_columns": ["updated_at", "ingestion_ts_utc", "__run_id"],
            "quality_rules": {
                "not_null": ["customer_id"],
                "expressions": [{"name": "valid_period", "expression": "updated_at IS NOT NULL", "severity": "abort", "message": "updated_at is required for SCD2 history."}],
            },
        }
    )


def _silver_snapshot_soft_delete(templates: dict[str, ContractTemplate]) -> None:
    ingestion = templates["silver_snapshot_soft_delete"]["ingestion"]
    source = dict(ingestion.get("source") or {})
    source["read"] = {"source_complete": True}
    ingestion.update({"source": source, "quality_rules": {"not_null": ["device_id"], "unique_key": ["device_id"]}})
