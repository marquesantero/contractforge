"""Platform-neutral quality rule semantics."""

from __future__ import annotations

ABORT_ONLY_RULES = frozenset({"required_columns", "unique_key", "min_rows", "row_count_minimum"})


def is_abort_only_failure(rule_name: str) -> bool:
    """Return whether a failed quality rule cannot isolate bad rows safely."""

    base = str(rule_name).split(":", 1)[0]
    return base in ABORT_ONLY_RULES
