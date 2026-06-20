"""Gold Databricks presets ported from ContractForge."""

from __future__ import annotations

from contractforge_databricks.presets.base import PRESET_META_KEY, Preset, meta

GOLD_PRESETS: dict[str, Preset] = {
    "gold_full_refresh": {
        PRESET_META_KEY: meta("gold_full_refresh", "gold", "ingestion", "Gold full refresh."),
        "layer": "gold",
        "mode": "overwrite",
        "schema_policy": "strict",
        "on_quality_fail": "fail",
    },
    "gold_partition_refresh": {
        PRESET_META_KEY: meta(
            "gold_partition_refresh",
            "gold",
            "ingestion",
            "Gold recalculated by partition.",
            ["extensions.databricks.partition_column", "extensions.databricks.partition_value"],
        ),
        "layer": "gold",
        "mode": "overwrite",
        "schema_policy": "strict",
        "on_quality_fail": "fail",
    },
    "gold_replace_partitions": {
        PRESET_META_KEY: meta(
            "gold_replace_partitions",
            "gold",
            "ingestion",
            "Gold declarative replacement of complete partitions.",
            ["extensions.databricks.merge_partition_column"],
        ),
        "layer": "gold",
        "mode": "upsert",
        "extensions": {
            "databricks": {
                "merge_strategy": "replace_partitions",
                "replace_partitions_source_complete": True,
            }
        },
        "schema_policy": "strict",
        "on_quality_fail": "fail",
    },
    "gold_snapshot_serving": {
        PRESET_META_KEY: meta("gold_snapshot_serving", "gold", "ingestion", "Gold snapshot serving.", ["merge_keys"]),
        "layer": "gold",
        "mode": "snapshot_reconcile_soft_delete",
        "schema_policy": "strict",
        "on_quality_fail": "fail",
    },
    "gold_current_state_serving": {
        PRESET_META_KEY: meta("gold_current_state_serving", "gold", "ingestion", "Gold current-state serving.", ["merge_keys"]),
        "layer": "gold",
        "mode": "upsert",
        "extensions": {"databricks": {"merge_strategy": "delta"}},
        "schema_policy": "strict",
        "on_quality_fail": "fail",
    },
}
