"""Databricks runtime presets ported from ContractForge."""

from __future__ import annotations

from contractforge_databricks.presets.base import PRESET_META_KEY, Preset, meta

RUNTIME_PRESETS: dict[str, Preset] = {
    "runtime_databricks_serverless": {
        PRESET_META_KEY: meta("runtime_databricks_serverless", "runtime", "runtime", "Databricks Serverless defaults."),
        "extensions": {"databricks": {"cache_source": False, "optimize_after_write": False}},
    },
    "runtime_spark_delta_local": {
        PRESET_META_KEY: meta("runtime_spark_delta_local", "runtime", "runtime", "Local PySpark + Delta defaults."),
        "extensions": {
            "databricks": {
                "cache_source": False,
                "optimize_after_write": False,
                "lock_enabled": False,
            }
        },
    },
}
