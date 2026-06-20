"""Platform-neutral write mode helpers."""

from __future__ import annotations

from contractforge_core.config import CUSTOM_WRITE_MODE_PREFIX, canonical_write_mode

WRITE_MODE_STRATEGY_LABELS = {
    "scd0_append": "APPEND",
    "scd0_overwrite": "OVERWRITE",
    "scd1_upsert": "MERGE",
    "scd1_hash_diff": "HASH_DIFF_APPEND",
    "scd2_historical": "SCD2_MERGE",
    "snapshot_soft_delete": "SNAPSHOT_MERGE",
}


def canonical_custom_write_mode(mode: str) -> str:
    """Return the canonical custom write mode name accepted by the core."""

    normalized = str(mode or "").strip()
    if not normalized:
        raise ValueError("custom write mode cannot be empty")
    if normalized.startswith(CUSTOM_WRITE_MODE_PREFIX):
        return normalized
    return f"{CUSTOM_WRITE_MODE_PREFIX}{normalized}"


def write_strategy_label(mode: str) -> str:
    """Map a logical write mode to a stable evidence label."""

    normalized = canonical_write_mode(mode)
    return WRITE_MODE_STRATEGY_LABELS.get(normalized, f"CUSTOM:{normalized}")
