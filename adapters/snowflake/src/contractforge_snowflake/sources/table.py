"""Table and view source rendering."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.naming import quote_multipart_identifier
from contractforge_snowflake.sources.models import SnowflakeSourcePlan


def render_table_source(contract: SemanticContract) -> SnowflakeSourcePlan:
    source = _source(contract)
    table = source.get("table") or source.get("name") or source.get("ref") or source.get("table_ref")
    if not table:
        raise ValueError("Snowflake table/view source requires source.table")
    source_type = str(source.get("type") or contract.source.kind or "table").lower()
    return SnowflakeSourcePlan(
        sql=f"SELECT * FROM {quote_multipart_identifier(str(table))}",
        metadata={"type": source_type, "table": str(table)},
    )


def _source(contract: SemanticContract) -> dict[str, Any]:
    return contract.source.raw or {}
