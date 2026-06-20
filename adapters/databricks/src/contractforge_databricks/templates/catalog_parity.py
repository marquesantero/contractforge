"""Additional templates ported from the original ContractForge catalog."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.templates.catalog import _access, _ann, _ops, _target, _template

ContractTemplate = dict[str, Any]

PARITY_CONTRACT_TEMPLATES: dict[str, ContractTemplate] = {
    "bronze_blob_partitioned_files": _template(
        "bronze_blob_partitioned_files",
        "bronze",
        "Bronze batch ingestion for partitioned files in object storage.",
        {
            "preset": "bronze_file_append",
            "source": {
                "type": "s3",
                "format": "parquet",
                "path": "s3://company-landing/orders/",
                "options": {"recursiveFileLookup": True, "pathGlobFilter": "*.parquet"},
                "read": {
                    "source_complete": True,
                    "schema": "order_id STRING, order_date DATE, customer_id STRING, amount DOUBLE",
                    "file_regex": r"^year=2026/month=05/.*/orders_\d+\.parquet$",
                    "file_regex_scope": "relative_path",
                    "file_regex_max_listed": 50000,
                },
            },
            "target": _target("raw", "b_orders_files"),
            "layer": "bronze",
            "mode": "scd0_append",
            "schema_policy": "additive_only",
            "quality_rules": {
                "not_null": ["order_id"],
                "expressions": [
                    {
                        "name": "valid_amount",
                        "expression": "amount IS NULL OR amount >= 0",
                        "severity": "warn",
                        "message": "Negative amount in raw file.",
                    }
                ],
            },
        },
        annotations=_ann("Partitioned order files in object storage."),
        operations=_ops("b_orders_files"),
    ),
    "silver_scd1_hash_diff": _template(
        "silver_scd1_hash_diff",
        "silver",
        "Silver append-only hash diff retaining changed versions.",
        {
            "preset": "silver_hash_diff_append",
            "source": {"type": "table", "table": "main.raw.b_products"},
            "target": _target("curated", "s_products_hash_diff"),
            "layer": "silver",
            "mode": "scd1_hash_diff",
            "hash_keys": ["product_id"],
            "hash_exclude_columns": ["updated_at"],
            "transform": {
                "deduplicate": {
                    "keys": ["product_id"],
                    "order_by": "updated_at DESC NULLS LAST",
                }
            },
            "quality_rules": {
                "not_null": ["product_id"],
                "expressions": [
                    {
                        "name": "valid_product_status",
                        "expression": "status IS NULL OR status IN ('active', 'inactive', 'discontinued')",
                        "severity": "quarantine",
                        "message": "Invalid product status.",
                    }
                ],
            },
        },
        annotations=_ann("Changed product versions detected by hash diff."),
        operations=_ops("s_products_hash_diff"),
        access=_access("catalog-analytics"),
        priority=10,
    ),
}
