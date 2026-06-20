"""Databricks modifier presets ported from ContractForge."""

from __future__ import annotations

from contractforge_databricks.presets.base import PRESET_META_KEY, Preset, meta

DELTA_PRESETS: dict[str, Preset] = {
    "delta_cdf_enabled": {
        PRESET_META_KEY: meta("delta_cdf_enabled", "delta", "modifier", "Enable Delta Change Data Feed."),
        "extensions": {"databricks": {"delta_properties": {"delta.enableChangeDataFeed": "true"}}},
    },
    "delta_optimized_writes": {
        PRESET_META_KEY: meta("delta_optimized_writes", "delta", "modifier", "Optimized Delta write properties."),
        "extensions": {
            "databricks": {
                "delta_properties": {
                    "delta.autoOptimize.optimizeWrite": "true",
                    "delta.autoOptimize.autoCompact": "true",
                }
            }
        },
    },
    "delta_liquid_clustering": {
        PRESET_META_KEY: meta(
            "delta_liquid_clustering",
            "delta",
            "modifier",
            "Databricks Delta liquid clustering.",
            ["extensions.databricks.cluster_columns"],
        )
    },
}

QUALITY_PRESETS: dict[str, Preset] = {
    "quality_strict": {
        PRESET_META_KEY: meta("quality_strict", "quality", "modifier", "Abortive quality policy."),
        "on_quality_fail": "fail",
    },
    "quality_quarantine": {
        PRESET_META_KEY: meta("quality_quarantine", "quality", "modifier", "Quality quarantine policy."),
        "on_quality_fail": "quarantine",
    },
}

GOVERNANCE_PRESETS: dict[str, Preset] = {
    "governance_uc_basic": {
        PRESET_META_KEY: meta("governance_uc_basic", "governance", "modifier", "Basic Unity Catalog governance."),
        "annotations": {"policy": "warn"},
        "access": {"access_policy": {"mode": "validate_only", "on_drift": "warn"}},
    }
}
