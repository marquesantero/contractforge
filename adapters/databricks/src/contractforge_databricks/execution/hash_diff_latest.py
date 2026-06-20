"""Target-latest selection helpers for SCD1 hash-diff writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.runtime import QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.sql import quote_identifier, quote_table_name


@dataclass(frozen=True)
class HashDiffLatestSelection:
    order_by: str | None = None
    reason: str = "none"


def resolve_hash_diff_latest_selection(
    contract: SemanticContract,
    target_schema: dict[str, str] | None = None,
) -> HashDiffLatestSelection:
    explicit = _explicit_order_by(contract)
    if explicit:
        return HashDiffLatestSelection(explicit, "contract")
    columns = set(target_schema or {})
    if "ingestion_sequence" in columns:
        return HashDiffLatestSelection("ingestion_sequence DESC NULLS LAST", "ingestion_sequence")
    if "ingestion_ts_utc" in columns:
        if "__run_id" in columns:
            return HashDiffLatestSelection(
                "ingestion_ts_utc DESC NULLS LAST, __run_id DESC NULLS LAST",
                "ingestion_ts_utc",
            )
        return HashDiffLatestSelection("ingestion_ts_utc DESC NULLS LAST", "ingestion_ts_utc")
    if "source_loaded_at_utc" in columns:
        return HashDiffLatestSelection("source_loaded_at_utc DESC NULLS LAST", "source_loaded_at_utc")
    return HashDiffLatestSelection()


def validate_hash_diff_target_latest(
    *,
    query_one: QueryOne | None,
    target_table: str,
    merge_keys: tuple[str, ...],
    selection: HashDiffLatestSelection,
) -> None:
    if query_one is None:
        return
    if selection.reason == "ingestion_ts_utc":
        ambiguous = query_one(render_null_ingestion_ts_ambiguity_sql(target_table, merge_keys))
        if _count(ambiguous):
            raise ValueError(
                "scd1_hash_diff found multiple target versions per key with null ingestion_ts_utc. "
                "Provide transform.deduplicate.order_by for history migration or rewrite the target with "
                "ingestion_ts_utc/ingestion_sequence."
            )
    if selection.order_by is None:
        duplicate = query_one(render_hash_diff_duplicate_target_keys_sql(target_table, merge_keys))
        if _count(duplicate):
            raise ValueError(
                "scd1_hash_diff found multiple target versions per key, but no deterministic ordering exists "
                "to select the latest state. Provide transform.deduplicate.order_by or rewrite the target with "
                "ingestion_ts_utc/ingestion_sequence."
            )


def render_null_ingestion_ts_ambiguity_sql(target_table: str, hash_keys: tuple[str, ...]) -> str:
    keys = ", ".join(quote_identifier(key) for key in hash_keys)
    return "\n".join(
        [
            "SELECT COUNT(*) AS ambiguous_key_count",
            "FROM (",
            f"  SELECT {keys}, COUNT(*) AS __cnt, MAX({quote_identifier('ingestion_ts_utc')}) AS __max_ingestion_ts_utc",
            f"  FROM {quote_table_name(target_table)}",
            f"  GROUP BY {keys}",
            ") target_versions",
            "WHERE __cnt > 1 AND __max_ingestion_ts_utc IS NULL",
        ]
    )


def render_hash_diff_duplicate_target_keys_sql(target_table: str, hash_keys: tuple[str, ...]) -> str:
    keys = ", ".join(quote_identifier(key) for key in hash_keys)
    return "\n".join(
        [
            "SELECT COUNT(*) AS duplicate_key_count",
            "FROM (",
            f"  SELECT {keys}, COUNT(*) AS __cnt",
            f"  FROM {quote_table_name(target_table)}",
            f"  GROUP BY {keys}",
            ") target_versions",
            "WHERE __cnt > 1",
        ]
    )


def _explicit_order_by(contract: SemanticContract) -> str | None:
    deduplicate = contract.transform.raw.get("deduplicate") if contract.transform else None
    if not isinstance(deduplicate, dict):
        return None
    merge_keys = contract.write.merge_keys or contract.write.hash_keys
    keys = _as_tuple(deduplicate.get("keys"))
    if keys and keys != merge_keys:
        return None
    return _render_order_by(deduplicate.get("order_by"))


def _render_order_by(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if not isinstance(value, list):
        return None
    parts: list[str] = []
    for item in value:
        if not isinstance(item, dict) or not item.get("column"):
            continue
        clause = quote_identifier(str(item["column"]))
        clause += f" {str(item.get('direction', 'desc')).upper()}"
        if item.get("nulls"):
            clause += f" NULLS {str(item['nulls']).upper()}"
        parts.append(clause)
    return ", ".join(parts) or None


def _as_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _count(row: dict[str, Any] | None) -> int:
    if not row:
        return 0
    for value in row.values():
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0
