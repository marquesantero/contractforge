"""Silver Databricks presets ported from ContractForge."""

from __future__ import annotations

from contractforge_databricks.presets.base import PRESET_META_KEY, Preset, meta

SILVER_PRESETS: dict[str, Preset] = {
    "silver_scd1_upsert": {
        PRESET_META_KEY: meta("silver_scd1_upsert", "silver", "ingestion", "Silver current-state Delta MERGE.", ["merge_keys"]),
        "layer": "silver",
        "mode": "upsert",
        "extensions": {"databricks": {"merge_strategy": "delta"}},
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
    "silver_scd1_partition_upsert": {
        PRESET_META_KEY: meta(
            "silver_scd1_partition_upsert",
            "silver",
            "ingestion",
            "Silver current-state MERGE pruned by partition.",
            ["merge_keys", "extensions.databricks.merge_partition_column"],
        ),
        "layer": "silver",
        "mode": "upsert",
        "extensions": {"databricks": {"merge_strategy": "delta_by_partition"}},
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
    "silver_replace_partitions": {
        PRESET_META_KEY: meta(
            "silver_replace_partitions",
            "silver",
            "ingestion",
            "Silver replacement of complete partitions.",
            ["extensions.databricks.merge_partition_column"],
        ),
        "layer": "silver",
        "mode": "upsert",
        "extensions": {
            "databricks": {
                "merge_strategy": "replace_partitions",
                "replace_partitions_source_complete": True,
            }
        },
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
    "silver_incremental_watermark_upsert": {
        PRESET_META_KEY: meta(
            "silver_incremental_watermark_upsert",
            "silver",
            "ingestion",
            "Silver current-state incremental watermark upsert.",
            ["merge_keys", "watermark_columns"],
        ),
        "layer": "silver",
        "mode": "upsert",
        "extensions": {"databricks": {"merge_strategy": "delta"}},
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
    "silver_hash_diff_append": {
        PRESET_META_KEY: meta("silver_hash_diff_append", "silver", "ingestion", "Silver hash-diff append.", ["hash_keys"]),
        "layer": "silver",
        "mode": "hash_diff_upsert",
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
        "hash_exclude_columns": ["ingestion_ts_utc", "__run_id"],
    },
    "silver_quarantine_ingestion": {
        PRESET_META_KEY: meta(
            "silver_quarantine_ingestion",
            "silver",
            "ingestion",
            "Silver current-state merge with quarantine for row-level rules.",
            ["merge_keys"],
        ),
        "layer": "silver",
        "mode": "upsert",
        "extensions": {"databricks": {"merge_strategy": "delta"}},
        "schema_policy": "additive_only",
        "on_quality_fail": "quarantine",
    },
    "silver_snapshot_soft_delete": {
        PRESET_META_KEY: meta(
            "silver_snapshot_soft_delete", "silver", "ingestion", "Silver snapshot soft delete.", ["merge_keys"]
        ),
        "layer": "silver",
        "mode": "snapshot_reconcile_soft_delete",
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
    "silver_historical": {
        PRESET_META_KEY: meta("silver_historical", "silver", "ingestion", "Silver historical versioning.", ["merge_keys"]),
        "layer": "silver",
        "mode": "historical",
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
}
