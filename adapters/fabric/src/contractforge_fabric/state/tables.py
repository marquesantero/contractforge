"""Fabric operational state table names."""

from __future__ import annotations

from contractforge_core.evidence import STATE_TABLES


def state_table_names(schema: str = "contractforge") -> dict[str, str]:
    return {name: f"{schema}.{table}" for name, table in STATE_TABLES.items()}


__all__ = ["state_table_names"]
