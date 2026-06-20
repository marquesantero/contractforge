"""Snowflake SCD1 upsert write mode."""

from __future__ import annotations

from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.write_modes.models import SnowflakeWriteContext
from contractforge_snowflake.write_modes.validation import validate_merge_columns


def render_upsert_sql(context: SnowflakeWriteContext) -> str:
    merge_keys = context.contract.write.merge_keys
    if not merge_keys:
        raise ValueError("Snowflake scd1_upsert runtime requires merge_keys")
    columns = context.source_columns
    validate_merge_columns("scd1_upsert", merge_keys, columns)
    update_columns = tuple(column for column in columns if column not in set(merge_keys)) or tuple(merge_keys)
    on_clause = " AND ".join(f"target.{quote_identifier(key)} = source.{quote_identifier(key)}" for key in merge_keys)
    update_clause = ", ".join(f"target.{quote_identifier(column)} = source.{quote_identifier(column)}" for column in update_columns)
    insert_columns = ", ".join(quote_identifier(column) for column in columns)
    insert_values = ", ".join(f"source.{quote_identifier(column)}" for column in columns)
    return "\n".join(
        (
            f"MERGE INTO {context.target} AS target",
            f"USING (\n{context.source_sql}\n) AS source",
            f"ON {on_clause}",
            f"WHEN MATCHED THEN UPDATE SET {update_clause}",
            f"WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})",
        )
    )


__all__ = ["render_upsert_sql"]
