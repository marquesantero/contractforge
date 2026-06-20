"""Databricks SCD2 delete-expression merge helpers."""

from __future__ import annotations

from contractforge_databricks.execution.scd2_late import late_arriving_condition, late_arriving_filter
from contractforge_databricks.sql import quote_identifier, quote_table_name


def render_scd2_delete_merge_sql(
    *,
    target_table: str,
    source_view: str,
    merge_keys: tuple[str, ...],
    apply_as_deletes: str,
    sequence_by: str | None = None,
    late_arriving_policy: str = "apply",
) -> str:
    if not merge_keys:
        raise ValueError("SCD2 delete handling requires merge_keys")
    if not apply_as_deletes or not apply_as_deletes.strip():
        raise ValueError("SCD2 delete handling requires scd2_apply_as_deletes")
    key_list = ", ".join(quote_identifier(key) for key in merge_keys)
    key_join = " AND ".join(f"t.{quote_identifier(key)} <=> d.{quote_identifier(key)}" for key in merge_keys)
    joined_key_join = " AND ".join(f"t.{quote_identifier(key)} <=> d.{quote_identifier(key)}" for key in merge_keys)
    source_sequence = f", {quote_identifier(sequence_by)}" if sequence_by else ""
    target_sequence = f", {quote_identifier(sequence_by)} AS `__tgt_sequence`" if sequence_by else ""
    joined_sequence = ", t.`__tgt_sequence`" if sequence_by else ""
    reject_cte = _reject_cte(sequence_by, late_arriving_policy)
    reject_join = " CROSS JOIN reject_late_arriving" if sequence_by and late_arriving_policy == "reject" else ""
    return "\n".join(
        [
            f"MERGE INTO {quote_table_name(target_table)} t",
            "USING (",
            "  WITH delete_candidates AS (",
            f"    SELECT DISTINCT {key_list}{source_sequence}",
            f"    FROM {quote_table_name(source_view)}",
            f"    WHERE coalesce(CAST(({apply_as_deletes}) AS BOOLEAN), false)",
            "  ), target_current AS (",
            f"    SELECT {key_list}{target_sequence}",
            f"    FROM {quote_table_name(target_table)}",
            "    WHERE `is_current` = true",
            "  ), joined AS (",
            f"    SELECT d.*{joined_sequence} FROM delete_candidates d",
            f"    LEFT JOIN target_current t ON {joined_key_join}",
            f"  ){reject_cte}",
            f"  SELECT {key_list} FROM joined{reject_join}",
            f"  WHERE {late_arriving_filter(sequence_by, late_arriving_policy)}",
            ") d",
            f"ON {key_join} AND t.`is_current` = true",
            "WHEN MATCHED THEN UPDATE SET",
            "  t.`valid_to` = current_timestamp(),",
            "  t.`is_current` = false,",
            "  t.`changed_columns` = 'DELETE'",
        ]
    )


def _reject_cte(sequence_by: str | None, policy: str) -> str:
    if not sequence_by or policy != "reject":
        return ""
    return (
        "\n  , late_arriving AS (\n    SELECT count(*) AS late_count FROM joined\n    WHERE "
        + late_arriving_condition(sequence_by)
        + "\n  ), reject_late_arriving AS (\n    SELECT CASE WHEN late_count > 0 THEN 1 / 0 ELSE 0 END AS __late_guard FROM late_arriving\n  )"
    )
