"""Bronze Databricks presets ported from ContractForge."""

from __future__ import annotations

from contractforge_databricks.presets.base import PRESET_META_KEY, Preset, meta

BRONZE_PRESETS: dict[str, Preset] = {
    "bronze_file_append": {
        PRESET_META_KEY: meta("bronze_file_append", "bronze", "ingestion", "Bronze append for batch files."),
        "layer": "bronze",
        "mode": "append",
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
    "bronze_table_append": {
        PRESET_META_KEY: meta("bronze_table_append", "bronze", "ingestion", "Bronze append for table replication."),
        "layer": "bronze",
        "mode": "append",
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
    "bronze_autoloader_append": {
        PRESET_META_KEY: meta(
            "bronze_autoloader_append",
            "bronze",
            "ingestion",
            "Bronze available-now Auto Loader append.",
            ["source.path", "source.progress_location", "source.schema_tracking_location", "target_table"],
        ),
        "source": {"type": "incremental_files", "trigger": "available_now", "format": "parquet"},
        "layer": "bronze",
        "mode": "append",
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
        "idempotency_policy": "skip_if_success",
    },
    "bronze_full_overwrite": {
        PRESET_META_KEY: meta("bronze_full_overwrite", "bronze", "ingestion", "Bronze full snapshot overwrite."),
        "layer": "bronze",
        "mode": "overwrite",
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
    "bronze_partition_overwrite": {
        PRESET_META_KEY: meta(
            "bronze_partition_overwrite",
            "bronze",
            "ingestion",
            "Bronze overwrite for one controlled partition.",
            ["extensions.databricks.partition_column", "extensions.databricks.partition_value"],
        ),
        "layer": "bronze",
        "mode": "overwrite",
        "schema_policy": "additive_only",
        "on_quality_fail": "fail",
    },
}
