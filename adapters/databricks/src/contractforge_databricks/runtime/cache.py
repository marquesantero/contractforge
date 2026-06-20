"""Prepared source cache helpers for Databricks bundle execution."""

from __future__ import annotations

from typing import Any

from contractforge_core.runtime import PreparedInput
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.runtime.spark import safe_cache_table, safe_uncache_table


def cache_prepared_source_if_requested(spark: Any, contract: Any, prepared: PreparedInput) -> bool:
    if not bool(databricks_extensions(contract).get("cache_source")):
        return False
    return safe_cache_table(spark, prepared.source_view)


def uncache_prepared_source_if_needed(spark: Any, prepared: PreparedInput, cached: bool) -> None:
    if cached:
        safe_uncache_table(spark, prepared.source_view)
