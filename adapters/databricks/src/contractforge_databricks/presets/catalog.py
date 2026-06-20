"""Databricks-owned preset catalog ported from ContractForge."""

from __future__ import annotations

from contractforge_databricks.presets.base import PRESET_META_KEY as PRESET_META_KEY, Preset
from contractforge_databricks.presets.bronze import BRONZE_PRESETS
from contractforge_databricks.presets.gold import GOLD_PRESETS
from contractforge_databricks.presets.modifiers import DELTA_PRESETS, GOVERNANCE_PRESETS, QUALITY_PRESETS
from contractforge_databricks.presets.runtime import RUNTIME_PRESETS
from contractforge_databricks.presets.silver import SILVER_PRESETS
from contractforge_databricks.presets.write_engine import WRITE_ENGINE_PRESETS

BUILTIN_PRESETS: dict[str, Preset] = {
    **BRONZE_PRESETS,
    **SILVER_PRESETS,
    **GOLD_PRESETS,
    **QUALITY_PRESETS,
    **DELTA_PRESETS,
    **GOVERNANCE_PRESETS,
    **RUNTIME_PRESETS,
    **WRITE_ENGINE_PRESETS,
}
