"""Registry for Snowflake runtime write modes."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.write_modes.append import render_append_sql
from contractforge_snowflake.write_modes.hash_diff import render_hash_diff_sql
from contractforge_snowflake.write_modes.models import SnowflakeWriteContext, SnowflakeWriteModeStrategy
from contractforge_snowflake.write_modes.overwrite import render_overwrite_sql
from contractforge_snowflake.write_modes.upsert import render_upsert_sql
from contractforge_snowflake.write_modes.validation import validate_merge_source


def render_write_sql(context: SnowflakeWriteContext) -> str:
    strategy = snowflake_write_strategy(context.contract.write.mode)
    if strategy is None:
        raise NotImplementedError(f"Snowflake runtime write mode is not implemented: {context.contract.write.mode}")
    return strategy.render_sql(context)


def target_bootstrap_commands(
    contract: SemanticContract,
    *,
    source_sql: str,
    target: str,
) -> tuple[str, ...]:
    strategy = snowflake_write_strategy(contract.write.mode)
    if strategy is None or strategy.bootstrap_sql is None:
        return ()
    return (strategy.bootstrap_sql(source_sql, target),)


def prewrite_validation_commands(context: SnowflakeWriteContext) -> tuple[str, ...]:
    strategy = snowflake_write_strategy(context.contract.write.mode)
    if strategy is None or strategy.prewrite_validator is None:
        return ()
    return strategy.prewrite_validator(context)


def snowflake_write_strategy(write_mode: str) -> SnowflakeWriteModeStrategy | None:
    return _WRITE_MODE_STRATEGIES.get(write_mode)


def create_target_if_missing_sql(source_sql: str, target: str) -> str:
    return f"CREATE TABLE IF NOT EXISTS {target} AS\nSELECT * FROM (\n{source_sql}\n) AS _CF_SOURCE\nWHERE 1 = 0"


_APPEND = SnowflakeWriteModeStrategy(render_sql=render_append_sql, bootstrap_sql=create_target_if_missing_sql)
_OVERWRITE = SnowflakeWriteModeStrategy(render_sql=render_overwrite_sql)
_UPSERT = SnowflakeWriteModeStrategy(
    render_sql=render_upsert_sql,
    bootstrap_sql=create_target_if_missing_sql,
    prewrite_validator=validate_merge_source,
)
_HASH_DIFF = SnowflakeWriteModeStrategy(
    render_sql=render_hash_diff_sql,
    bootstrap_sql=create_target_if_missing_sql,
    prewrite_validator=validate_merge_source,
)

_WRITE_MODE_STRATEGIES: dict[str, SnowflakeWriteModeStrategy] = {
    "append": _APPEND,
    "scd0_append": _APPEND,
    "overwrite": _OVERWRITE,
    "scd0_overwrite": _OVERWRITE,
    "scd1_upsert": _UPSERT,
    "scd1_hash_diff": _HASH_DIFF,
}


__all__ = [
    "create_target_if_missing_sql",
    "prewrite_validation_commands",
    "render_write_sql",
    "snowflake_write_strategy",
    "target_bootstrap_commands",
]
