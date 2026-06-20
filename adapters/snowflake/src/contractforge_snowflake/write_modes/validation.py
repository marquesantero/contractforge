"""Shared Snowflake merge-source validation."""

from __future__ import annotations

from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.write_modes.models import SnowflakeWriteContext


def validate_merge_source(context: SnowflakeWriteContext) -> tuple[str, ...]:
    merge_keys = context.contract.write.merge_keys
    if not merge_keys:
        raise ValueError(f"Snowflake {context.contract.write.mode} runtime requires merge_keys")
    validate_merge_columns(context.contract.write.mode, merge_keys, context.source_columns)
    null_sql = merge_key_null_count_sql(context.source_sql, merge_keys)
    null_rows = context.scalar_int(context.session, null_sql)
    if null_rows:
        raise ValueError(
            f"Snowflake {context.contract.write.mode} source contains {null_rows} rows with null merge_keys: {list(merge_keys)}"
        )
    duplicate_sql = merge_key_duplicate_count_sql(context.source_sql, merge_keys)
    duplicate_groups = context.scalar_int(context.session, duplicate_sql)
    if duplicate_groups:
        raise ValueError(
            f"Snowflake {context.contract.write.mode} source contains duplicate merge_keys across "
            f"{duplicate_groups} groups: {list(merge_keys)}"
        )
    return (null_sql, duplicate_sql)


def validate_merge_columns(write_mode: str, merge_keys: tuple[str, ...], source_columns: tuple[str, ...]) -> None:
    if not source_columns:
        raise ValueError(f"Snowflake {write_mode} runtime could not resolve source columns")
    missing = tuple(key for key in merge_keys if key not in source_columns)
    if missing:
        raise ValueError(f"Snowflake {write_mode} source is missing merge key columns: {missing}")


def merge_key_null_count_sql(source_sql: str, merge_keys: tuple[str, ...]) -> str:
    condition = " OR ".join(f"{quote_identifier(key)} IS NULL" for key in merge_keys)
    return f"SELECT COUNT(*) FROM (\n{source_sql}\n) AS _CF_SOURCE\nWHERE {condition}"


def merge_key_duplicate_count_sql(source_sql: str, merge_keys: tuple[str, ...]) -> str:
    key_list = ", ".join(quote_identifier(key) for key in merge_keys)
    return (
        "SELECT COUNT(*) FROM (\n"
        f"  SELECT {key_list}, COUNT(*) AS _CF_ROW_COUNT\n"
        f"  FROM (\n{source_sql}\n) AS _CF_SOURCE\n"
        f"  GROUP BY {key_list}\n"
        "  HAVING COUNT(*) > 1\n"
        ") AS _CF_DUPLICATE_KEYS"
    )


__all__ = [
    "merge_key_duplicate_count_sql",
    "merge_key_null_count_sql",
    "validate_merge_columns",
    "validate_merge_source",
]
