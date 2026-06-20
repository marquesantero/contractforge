"""Inline SQL source rendering."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.sources.models import SnowflakeSourcePlan


def render_sql_source(contract: SemanticContract) -> SnowflakeSourcePlan:
    source = _source(contract)
    query = source.get("query") or source.get("sql")
    if not query:
        raise ValueError("Snowflake sql source requires source.query or source.sql")
    return SnowflakeSourcePlan(
        sql=str(query).strip().rstrip(";"),
        metadata={"type": "sql", "query_present": True},
    )


def _source(contract: SemanticContract) -> dict[str, Any]:
    return contract.source.raw or {}
