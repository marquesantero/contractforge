"""Prepared-source safety checks for Databricks MERGE writes."""

from __future__ import annotations

from typing import Any

from contractforge_core.quality import QualityRuleResult, quality_status
from contractforge_core.runtime import PreparedInput, QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.sql import quote_identifier, quote_table_name

MERGE_WRITE_MODES = {"scd1_upsert", "scd2_historical", "snapshot_soft_delete"}


def validate_merge_source_safety(
    *,
    contract: SemanticContract,
    prepared: PreparedInput,
    query_one: QueryOne | None,
    quality_results: tuple[QualityRuleResult, ...] = (),
) -> dict[str, Any]:
    """Validate source key safety before executing Databricks MERGE patterns."""
    if contract.write.mode not in MERGE_WRITE_MODES:
        return {"status": "SKIPPED", "reason": "not_merge_mode"}
    if query_one is None:
        return {"status": "SKIPPED", "reason": "query_one_not_configured"}
    if not contract.write.merge_keys or prepared.rows_read <= 0:
        return {"status": "SKIPPED", "reason": "no_merge_keys_or_rows"}

    _validate_columns(contract.write.merge_keys, prepared.source_columns)
    null_row = query_one(render_merge_key_nulls_sql(prepared.source_view, contract.write.merge_keys))
    all_null_count = _int_row_value(null_row, "all_keys_null_rows")
    if all_null_count == prepared.rows_read:
        raise ValueError(
            f"mode={contract.write.mode} received {prepared.rows_read} rows with fully null merge_keys. "
            f"keys={list(contract.write.merge_keys)}. Fix the source or add quality_rules.not_null."
        )

    if _skip_duplicate_check(contract, quality_results):
        return {"status": "PASSED", "all_null_key_rows": all_null_count, "duplicate_check": "SKIPPED"}

    duplicate_row = query_one(render_merge_key_duplicates_sql(prepared.source_view, contract.write.merge_keys))
    duplicate_groups = _int_row_value(duplicate_row, "duplicate_key_groups")
    duplicate_rows = _int_row_value(duplicate_row, "duplicate_rows")
    if duplicate_groups:
        raise ValueError(
            f"mode={contract.write.mode} received {duplicate_rows} duplicate source rows across "
            f"{duplicate_groups} merge_key groups. keys={list(contract.write.merge_keys)}. "
            "Fix the composite key, declare quality_rules.unique_key, or apply transform.deduplicate."
        )
    return {"status": "PASSED", "all_null_key_rows": all_null_count, "duplicate_key_groups": duplicate_groups}


def render_merge_key_nulls_sql(source_view: str, merge_keys: tuple[str, ...]) -> str:
    all_keys_null = " AND ".join(f"{quote_identifier(key)} IS NULL" for key in merge_keys)
    return (
        f"SELECT count(*) AS all_keys_null_rows "
        f"FROM {quote_table_name(source_view)} WHERE {all_keys_null}"
    )


def render_merge_key_duplicates_sql(source_view: str, merge_keys: tuple[str, ...]) -> str:
    key_list = ", ".join(quote_identifier(key) for key in merge_keys)
    return (
        "SELECT count(*) AS duplicate_key_groups, coalesce(sum(row_count), 0) AS duplicate_rows "
        f"FROM (SELECT {key_list}, count(*) AS row_count FROM {quote_table_name(source_view)} "
        f"GROUP BY {key_list} HAVING count(*) > 1)"
    )


def _validate_columns(keys: tuple[str, ...], source_columns: tuple[str, ...]) -> None:
    if not source_columns:
        return
    missing = [key for key in keys if key not in source_columns]
    if missing:
        raise ValueError(f"merge_keys missing from prepared source columns: {missing}")


def _skip_duplicate_check(contract: SemanticContract, quality_results: tuple[QualityRuleResult, ...]) -> bool:
    if quality_status(quality_results) != "PASSED":
        return False
    unique_rules = tuple(rule for rule in contract.quality if rule.rule == "unique_key")
    return any(set(rule.columns) == set(contract.write.merge_keys) for rule in unique_rules)


def _int_row_value(row: Any, key: str) -> int:
    if row is None:
        return 0
    if isinstance(row, dict):
        value = row.get(key)
    elif hasattr(row, "asDict"):
        value = row.asDict().get(key)
    else:
        value = getattr(row, key, None)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
