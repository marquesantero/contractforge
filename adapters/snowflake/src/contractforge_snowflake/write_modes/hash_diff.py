"""Snowflake SCD1 hash-diff write mode."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.write_modes.models import SnowflakeWriteContext
from contractforge_snowflake.write_modes.validation import validate_merge_columns


def render_hash_diff_sql(context: SnowflakeWriteContext) -> str:
    merge_keys = context.contract.write.merge_keys
    if not merge_keys:
        raise ValueError("Snowflake scd1_hash_diff runtime requires merge_keys")
    columns = context.source_columns
    validate_merge_columns("scd1_hash_diff", merge_keys, columns)
    hash_columns = hash_columns_for_contract(context.contract, columns=columns)
    update_columns = tuple(column for column in columns if column not in set(merge_keys)) or tuple(merge_keys)
    on_clause = " AND ".join(f"target.{quote_identifier(key)} = source.{quote_identifier(key)}" for key in merge_keys)
    change_clause = f"{hash_expr('target', hash_columns)} <> {hash_expr('source', hash_columns)}"
    update_clause = ", ".join(f"target.{quote_identifier(column)} = source.{quote_identifier(column)}" for column in update_columns)
    insert_columns = ", ".join(quote_identifier(column) for column in columns)
    insert_values = ", ".join(f"source.{quote_identifier(column)}" for column in columns)
    return "\n".join(
        (
            f"MERGE INTO {context.target} AS target",
            f"USING (\n{context.source_sql}\n) AS source",
            f"ON {on_clause}",
            f"WHEN MATCHED AND {change_clause} THEN UPDATE SET {update_clause}",
            f"WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})",
        )
    )


def hash_diff_candidate_count_sql(context: SnowflakeWriteContext) -> str:
    merge_keys = context.contract.write.merge_keys
    if not merge_keys:
        raise ValueError("Snowflake scd1_hash_diff runtime requires merge_keys")
    columns = context.source_columns
    validate_merge_columns("scd1_hash_diff", merge_keys, columns)
    hash_columns = hash_columns_for_contract(context.contract, columns=columns)
    on_clause = " AND ".join(f"target.{quote_identifier(key)} = source.{quote_identifier(key)}" for key in merge_keys)
    target_missing_clause = " AND ".join(f"target.{quote_identifier(key)} IS NULL" for key in merge_keys)
    change_clause = f"{hash_expr('target', hash_columns)} <> {hash_expr('source', hash_columns)}"
    return "\n".join(
        (
            "SELECT COUNT(*)",
            f"FROM (\n{context.source_sql}\n) AS source",
            f"LEFT JOIN {context.target} AS target",
            f"ON {on_clause}",
            f"WHERE ({target_missing_clause}) OR ({change_clause})",
        )
    )


def hash_columns_for_contract(contract: SemanticContract, *, columns: tuple[str, ...]) -> tuple[str, ...]:
    excluded = {*contract.write.merge_keys, *contract.write.hash_exclude_columns}
    candidates = contract.write.hash_keys if contract.write.hash_strategy == "explicit" else columns
    result = tuple(column for column in candidates if column in columns and column not in excluded)
    if not result:
        raise ValueError("Snowflake scd1_hash_diff runtime requires at least one hash input column")
    return result


def hash_expr(alias: str, columns: tuple[str, ...]) -> str:
    return "HASH(" + ", ".join(f"{alias}.{quote_identifier(column)}" for column in columns) + ")"


__all__ = ["hash_diff_candidate_count_sql", "hash_columns_for_contract", "hash_expr", "render_hash_diff_sql"]
