"""ContractForge-compatible SCD2 Delta MERGE SQL."""

from __future__ import annotations

from uuid import uuid4

from contractforge_core.semantic import SemanticContract
from contractforge_core.execution import ExecutionOutcome
from contractforge_databricks.execution.scd2_deletes import render_scd2_delete_merge_sql
from contractforge_databricks.execution.scd2_late import (
    joined_sequence_select,
    late_arriving_condition,
    late_arriving_filter,
    reject_guard_join,
    target_sequence_select,
)
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_identifier, quote_table_name


def render_scd2_merge_sql(
    *,
    target_table: str,
    source_view: str,
    merge_keys: tuple[str, ...],
    insert_columns: tuple[str, ...],
) -> str:
    """Render SCD2 MERGE over a prepared staging view.

    The staging view must already contain ContractForge-managed SCD2 columns:
    `valid_from`, `valid_to`, `is_current`, `row_hash`, and `changed_columns`.
    """
    if not merge_keys:
        raise ValueError("scd2_historical requires merge_keys")
    _require_columns(insert_columns, tuple(f"__merge_key_{key}" for key in merge_keys), "merge key staging columns")
    _require_columns(insert_columns, ("valid_from", "valid_to", "is_current", "row_hash", "changed_columns"))

    target_insert_columns = _target_insert_columns(insert_columns, merge_keys)
    key_condition = " AND ".join(
        f"t.{quote_identifier(key)} <=> s.{quote_identifier('__merge_key_' + key)}" for key in merge_keys
    )
    insert_cols = ", ".join(quote_identifier(column) for column in target_insert_columns)
    insert_vals = ", ".join(f"s.{quote_identifier(column)}" for column in target_insert_columns)
    changed_expr = _changed_columns_expr(target_insert_columns, merge_keys)

    return "\n".join(
        [
            f"MERGE INTO {quote_table_name(target_table)} t",
            f"USING {quote_table_name(source_view)} s",
            f"ON {key_condition} AND t.`is_current` = true",
            "WHEN MATCHED AND t.`row_hash` <> s.`row_hash` THEN UPDATE SET",
            "  t.`valid_to` = current_timestamp(),",
            "  t.`is_current` = false,",
            f"  t.`changed_columns` = {changed_expr}",
            f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})",
        ]
    )


def execute_scd2_merge(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    source_view: str,
    insert_columns: tuple[str, ...],
) -> ExecutionOutcome:
    if contract.write.mode != "scd2_historical":
        raise ValueError(f"execute_scd2_merge only supports scd2_historical, got {contract.write.mode}")
    target = target_full_name(contract)
    stage_view = f"__cf_scd2_stage_{uuid4().hex}"
    stage_statement = render_scd2_stage_sql(
        target_table=target,
        source_view=source_view,
        stage_view=stage_view,
        merge_keys=contract.write.merge_keys,
        source_columns=insert_columns,
        sequence_by=contract.write.scd2_sequence_by,
        late_arriving_policy=contract.write.scd2_late_arriving_policy,
        apply_as_deletes=contract.write.scd2_apply_as_deletes,
    )
    statement = render_scd2_merge_sql(
        target_table=target,
        source_view=stage_view,
        merge_keys=contract.write.merge_keys,
        insert_columns=insert_columns,
    )
    if contract.write.scd2_apply_as_deletes:
        runner.sql(
            render_scd2_delete_merge_sql(
                target_table=target,
                source_view=source_view,
                merge_keys=contract.write.merge_keys,
                apply_as_deletes=contract.write.scd2_apply_as_deletes,
                sequence_by=contract.write.scd2_sequence_by,
                late_arriving_policy=contract.write.scd2_late_arriving_policy,
            )
        )
    runner.sql(stage_statement)
    try:
        runner.sql(statement)
    finally:
        runner.sql(f"DROP VIEW IF EXISTS {quote_table_name(stage_view)}")
    return ExecutionOutcome(
        status="SUCCESS",
        operation="core_managed_scd2_delta_merge",
        target=target,
        metrics={
            "insert_columns": len(_target_insert_columns(insert_columns, contract.write.merge_keys)),
            "merge_keys": len(contract.write.merge_keys),
            "stage_view": stage_view,
        },
        sql=statement,
    )


def render_scd2_stage_sql(
    *,
    target_table: str,
    source_view: str,
    stage_view: str,
    merge_keys: tuple[str, ...],
    source_columns: tuple[str, ...],
    sequence_by: str | None = None,
    late_arriving_policy: str = "apply",
    apply_as_deletes: str | None = None,
) -> str:
    if not merge_keys:
        raise ValueError("scd2_historical requires merge_keys")
    _require_columns(source_columns, ("valid_from", "valid_to", "is_current", "row_hash", "changed_columns"))
    data_columns = _target_insert_columns(source_columns, merge_keys)
    if sequence_by and sequence_by not in data_columns:
        raise ValueError(f"prepared SCD2 source is missing scd2_sequence_by: {sequence_by}")
    key_join = " AND ".join(f"t.{quote_identifier(key)} <=> s.{quote_identifier(key)}" for key in merge_keys)
    target_keys = ", ".join(quote_identifier(key) for key in merge_keys)
    select_data = ", ".join(f"s.{quote_identifier(column)}" for column in data_columns)
    null_merge_keys = ", ".join(f"NULL AS {quote_identifier('__merge_key_' + key)}" for key in merge_keys)
    update_merge_keys = ", ".join(f"{quote_identifier(key)} AS {quote_identifier('__merge_key_' + key)}" for key in merge_keys)
    stage_columns = ", ".join(quote_identifier(column) for column in (*data_columns, *(f"__merge_key_{key}" for key in merge_keys)))

    lines = [
        f"CREATE OR REPLACE TEMP VIEW {quote_table_name(stage_view)} AS",
        "WITH target_current AS (",
        f"  SELECT {target_keys}, `row_hash` AS `__tgt_row_hash`{target_sequence_select(sequence_by)}",
        f"  FROM {quote_table_name(target_table)}",
        "  WHERE `is_current` = true",
        "), joined AS (",
        f"  SELECT {select_data}, t.`__tgt_row_hash`{joined_sequence_select(sequence_by)}",
        f"  FROM {quote_table_name(source_view)} s",
        f"  LEFT JOIN target_current t ON {key_join}",
        f"  WHERE {_non_delete_filter(apply_as_deletes)}",
        ")",
    ]
    if late_arriving_policy == "reject" and sequence_by:
        lines.extend(
            [
                ", late_arriving AS (",
                "  SELECT count(*) AS late_count FROM joined",
                f"  WHERE {late_arriving_condition(sequence_by)}",
                "), reject_late_arriving AS (",
                "  SELECT CASE WHEN late_count > 0 THEN 1 / 0 ELSE 0 END AS __late_guard FROM late_arriving",
                ")",
            ]
        )
    lines.extend(
        [
            ", changed AS (",
            f"  SELECT * FROM joined{reject_guard_join(sequence_by, late_arriving_policy)}",
            f"  WHERE {late_arriving_filter(sequence_by, late_arriving_policy)}",
            "    AND (`__tgt_row_hash` IS NULL OR NOT (`row_hash` <=> `__tgt_row_hash`))",
            "), insert_stage AS (",
            f"  SELECT {', '.join(quote_identifier(column) for column in data_columns)}, {null_merge_keys}",
            "  FROM changed",
            "), update_stage AS (",
            f"  SELECT {', '.join(quote_identifier(column) for column in data_columns)}, {update_merge_keys}",
            "  FROM changed WHERE `__tgt_row_hash` IS NOT NULL",
            ")",
            f"SELECT {stage_columns} FROM insert_stage",
            "UNION ALL",
            f"SELECT {stage_columns} FROM update_stage",
        ]
    )
    return "\n".join(lines)


def _require_columns(columns: tuple[str, ...], required: tuple[str, ...], context: str = "required columns") -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"prepared SCD2 source is missing {context}: {missing}")


def _target_insert_columns(columns: tuple[str, ...], merge_keys: tuple[str, ...]) -> tuple[str, ...]:
    staging_columns = {f"__merge_key_{key}" for key in merge_keys}
    return tuple(column for column in columns if column not in staging_columns)


def _changed_columns_expr(columns: tuple[str, ...], merge_keys: tuple[str, ...]) -> str:
    excluded = {*merge_keys, "valid_from", "valid_to", "is_current", "row_hash", "changed_columns"}
    candidates = tuple(column for column in columns if column not in excluded)
    if not candidates:
        return "s.`changed_columns`"
    parts = ", ".join(
        f"CASE WHEN NOT (t.{quote_identifier(column)} <=> s.{quote_identifier(column)}) "
        f"THEN '{column}' ELSE NULL END"
        for column in candidates
    )
    return f"concat_ws(',', {parts})"


def _non_delete_filter(apply_as_deletes: str | None) -> str:
    if not apply_as_deletes:
        return "true"
    return f"NOT coalesce(CAST(({apply_as_deletes}) AS BOOLEAN), false)"
