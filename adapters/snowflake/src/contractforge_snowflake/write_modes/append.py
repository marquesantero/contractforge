"""Snowflake append write mode."""

from __future__ import annotations

from contractforge_snowflake.write_modes.models import SnowflakeWriteContext


def render_append_sql(context: SnowflakeWriteContext) -> str:
    return f"INSERT INTO {context.target}\nSELECT * FROM (\n{context.source_sql}\n) AS _CF_SOURCE"


__all__ = ["render_append_sql"]
