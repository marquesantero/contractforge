"""Registry for Snowflake runtime source renderers."""

from __future__ import annotations

from typing import Callable

from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.sources.sql import render_sql_source
from contractforge_snowflake.sources.stage_files import render_stage_files_source
from contractforge_snowflake.sources.table import render_table_source
from contractforge_snowflake.sources.models import SnowflakeSourcePlan


SourceRenderer = Callable[[SemanticContract], SnowflakeSourcePlan]


def render_snowflake_source(contract: SemanticContract) -> SnowflakeSourcePlan:
    source_type = snowflake_source_type(contract)
    renderer = _SOURCE_RENDERERS.get(source_type)
    if renderer is None:
        raise NotImplementedError(f"Snowflake runtime source is not implemented: {source_type or 'unknown'}")
    return renderer(contract)


def snowflake_source_type(contract: SemanticContract) -> str:
    return str((contract.source.raw or {}).get("type") or contract.source.kind or "").lower()


_SOURCE_RENDERERS: dict[str, SourceRenderer] = {
    "table": render_table_source,
    "view": render_table_source,
    "sql": render_sql_source,
    "staged_files": render_stage_files_source,
    "snowflake_stage": render_stage_files_source,
    "stage_files": render_stage_files_source,
}
