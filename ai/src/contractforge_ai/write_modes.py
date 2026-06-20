"""Write-mode alias compatibility for AI-generated contracts."""

from __future__ import annotations

try:  # Prefer core when the installed version exposes the alias API.
    from contractforge_core.config import canonical_write_mode as canonical_write_mode
except Exception:  # pragma: no cover - compatibility for older core installs
    _ALIASES = {
        "append": "scd0_append",
        "overwrite": "scd0_overwrite",
        "upsert": "scd1_upsert",
        "merge_current": "scd1_upsert",
        "hash_diff_upsert": "scd1_hash_diff",
        "historical": "scd2_historical",
        "scd2": "scd2_historical",
        "snapshot_reconcile_soft_delete": "snapshot_soft_delete",
    }

    def canonical_write_mode(value: str) -> str:
        normalized = str(value or "").strip()
        if normalized.startswith("custom:"):
            return normalized
        alias_key = normalized.lower().replace("-", "_")
        return _ALIASES.get(alias_key, normalized)
