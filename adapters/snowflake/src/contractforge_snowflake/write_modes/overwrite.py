"""Snowflake overwrite write mode."""

from __future__ import annotations

from contractforge_snowflake.write_modes.models import SnowflakeWriteContext


def render_overwrite_sql(context: SnowflakeWriteContext) -> str:
    return f"CREATE OR REPLACE TABLE {context.target} AS\nSELECT * FROM (\n{context.source_sql}\n) AS _CF_SOURCE"


__all__ = ["render_overwrite_sql"]
