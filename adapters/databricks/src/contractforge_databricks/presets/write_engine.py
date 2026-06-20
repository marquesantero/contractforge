"""Databricks write-engine preview presets ported from ContractForge."""

from __future__ import annotations

from contractforge_databricks.presets.base import PRESET_META_KEY, Preset, meta

WRITE_ENGINE_PRESETS: dict[str, Preset] = {
    "write_engine_native_auto_preview": {
        PRESET_META_KEY: meta(
            "write_engine_native_auto_preview",
            "write_engine",
            "modifier",
            "Record Databricks native engine selection evidence without changing execution.",
        ),
        "extensions": {
            "databricks": {
                "write_engine": {"requested": "auto", "fallback_policy": "preview_only", "explain_selection": True}
            }
        },
    },
    "write_engine_databricks_sql_merge_preview": {
        PRESET_META_KEY: meta(
            "write_engine_databricks_sql_merge_preview",
            "write_engine",
            "modifier",
            "Preview Databricks SQL MERGE eligibility while executing the Delta baseline.",
            ["merge_keys"],
        ),
        "extensions": {
            "databricks": {
                "write_engine": {
                    "requested": "databricks_sql_merge",
                    "fallback_policy": "preview_only",
                    "explain_selection": True,
                }
            }
        },
    },
    "write_engine_lakeflow_auto_cdc_preview": {
        PRESET_META_KEY: meta(
            "write_engine_lakeflow_auto_cdc_preview",
            "write_engine",
            "modifier",
            "Preview Lakeflow AUTO CDC eligibility while executing the Delta baseline.",
            ["merge_keys"],
        ),
        "extensions": {
            "databricks": {
                "write_engine": {
                    "requested": "lakeflow_auto_cdc",
                    "fallback_policy": "preview_only",
                    "explain_selection": True,
                }
            }
        },
    },
}
