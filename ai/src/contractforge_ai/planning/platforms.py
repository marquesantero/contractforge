"""Shared platform hint detection for deterministic AI planning."""

from __future__ import annotations

PLATFORM_ALIASES: dict[str, tuple[str, ...]] = {
    "aws": ("aws", "glue", "athena", "lake formation", "emr"),
    "databricks": ("databricks", "asset bundle", "dab", "unity catalog", "autoloader"),
    "snowflake": ("snowflake",),
    "fabric": ("fabric", "onelake"),
    "gcp": ("gcp", "google cloud", "bigquery"),
}


def detect_platform_hints(text: str, signals: list[str] | None = None) -> list[str]:
    """Return platform hints inferred from user text in stable priority order."""

    lowered = text.lower()
    hints: list[str] = []
    for platform_name, aliases in PLATFORM_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            hints.append(platform_name)
            if signals is not None:
                signals.append(f"platform:{platform_name}")
    return hints
