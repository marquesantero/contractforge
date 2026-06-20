"""Databricks operational state table names."""

from __future__ import annotations

from contractforge_core.evidence import STATE_TABLES


def state_table_names(catalog: str, schema: str) -> dict[str, str]:
    return {name: f"{catalog}.{schema}.{table}" for name, table in STATE_TABLES.items()}
