"""Render BigQuery review artifacts for advanced write modes.

These artifacts are intentionally non-executable claims. They document the
candidate BigQuery algorithm and readback evidence needed before GCP can promote
hash-diff, historical or snapshot modes into the stable runtime surface.
"""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.preparation import (
    HASH_DELIMITER,
    HASH_NULL_SENTINEL,
    hash_diff_stage_spec_from_contract,
    resolved_hash_input_columns,
    scd2_stage_spec_from_contract,
    snapshot_stage_spec_from_contract,
)
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import identifier, public_mode, quote_table_ref, staging_table, target_table

_ADVANCED_MODES = {"scd1_hash_diff", "scd2_historical", "snapshot_soft_delete"}


def render_bigquery_advanced_write_mode_review(contract: SemanticContract, env: GCPEnvironment) -> str:
    """Render deterministic review metadata for non-stable BigQuery write modes."""

    mode = contract.write.mode
    if mode not in _ADVANCED_MODES:
        return ""

    source_columns = _source_columns(contract)
    blockers = _blockers(contract, source_columns)
    sql = _draft_sql(contract, env, source_columns) if not blockers else {}
    payload: dict[str, Any] = {
        "kind": "contractforge.gcp.bigquery_advanced_write_mode_review.v1",
        "status": "PLANNED_REVIEW_REQUIRED",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "mode": {
            "canonical": mode,
            "alias": public_mode(mode),
        },
        "execution": {
            "included": False,
            "reason": (
                "This is a deterministic BigQuery review artifact. The GCP adapter still blocks this "
                "write mode until real-account replay, idempotency and evidence parity pass."
            ),
        },
        "target": target_table(contract, env).strip("`"),
        "source": {
            "columns": list(source_columns),
            "requires_explicit_columns": True,
        },
        "merge_keys": list(contract.write.merge_keys),
        "blockers": blockers,
        "draft_sql": sql,
        "promotion_evidence_required": _promotion_evidence_required(mode),
        "review_boundaries": [
            "Do not execute this artifact as the stable GCP runtime path.",
            "Generated SQL is a candidate algorithm for review, not a certified write implementation.",
            "Promotion requires linked BigQuery job evidence and cross-adapter parity contracts.",
        ],
        "sources": [
            "https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax",
            "https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/hash_functions",
            "https://docs.cloud.google.com/bigquery/docs/access-historical-data",
        ],
    }
    payload.update(_mode_payload(contract, source_columns))
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_bigquery_advanced_write_sql(contract: SemanticContract, env: GCPEnvironment) -> str:
    """Render opt-in executable BigQuery SQL for review-required advanced write smokes."""

    mode = contract.write.mode
    if mode not in _ADVANCED_MODES:
        return ""

    source_columns = _source_columns(contract)
    blockers = _blockers(contract, source_columns)
    if blockers:
        reasons = "\n".join(f"-- {item['code']}: {item['message']}" for item in blockers)
        return f"-- Write mode `{public_mode(mode)}` is not executable for GCP BigQuery.\n{reasons}\n"
    if mode == "scd1_hash_diff":
        return _hash_diff_executable_sql(contract, env, source_columns)
    if mode == "scd2_historical":
        return _historical_executable_sql(contract, env, source_columns)
    if mode == "snapshot_soft_delete":
        return _snapshot_executable_sql(contract, env, source_columns)
    return ""


def _mode_payload(contract: SemanticContract, source_columns: tuple[str, ...]) -> dict[str, Any]:
    mode = contract.write.mode
    if mode == "scd1_hash_diff" and source_columns:
        spec = hash_diff_stage_spec_from_contract(contract, source_columns=source_columns)
        return {
            "hash_diff": {
                "hash_strategy": spec.hash_strategy,
                "hash_keys": list(spec.hash_keys),
                "hash_exclude_columns": list(spec.hash_exclude_columns),
                "hash_input_columns": list(resolved_hash_input_columns(contract, source_columns=source_columns)),
                "row_hash_column": spec.row_hash_column,
            }
        }
    if mode == "scd2_historical" and source_columns:
        spec = scd2_stage_spec_from_contract(contract, source_columns=source_columns)
        return {
            "historical": {
                "apply_as_deletes": contract.write.scd2_apply_as_deletes,
                "change_columns": list(spec.change_columns),
                "effective_from_column": spec.effective_from_column,
                "insert_columns": list(spec.insert_columns),
                "late_arriving_policy": spec.late_arriving_policy,
                "row_hash_column": spec.row_hash_column,
                "sequence_by": spec.sequence_by,
            }
        }
    if mode == "snapshot_soft_delete" and source_columns:
        spec = snapshot_stage_spec_from_contract(contract, source_columns=source_columns)
        return {
            "snapshot": {
                "deleted_at_column": spec.deleted_at_column,
                "is_active_column": spec.is_active_column,
                "row_hash_column": spec.row_hash_column,
                "source_columns": list(spec.source_columns),
            }
        }
    return {}


def _blockers(contract: SemanticContract, source_columns: tuple[str, ...]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if not contract.write.merge_keys:
        blockers.append({"code": "MISSING_MERGE_KEYS", "message": "Advanced BigQuery write-mode review requires merge_keys."})
    if not source_columns:
        blockers.append(
            {
                "code": "MISSING_SOURCE_COLUMNS",
                "message": "Declare top-level select_columns or source.read.columns so review SQL has deterministic columns.",
            }
        )
    if contract.write.mode == "scd1_hash_diff" and contract.write.hash_strategy != "all_columns_except" and not contract.write.hash_keys:
        blockers.append(
            {
                "code": "MISSING_HASH_KEYS",
                "message": "hash_diff_upsert requires hash_keys unless hash_strategy is all_columns_except.",
            }
        )
    if (
        contract.write.mode == "scd2_historical"
        and contract.write.scd2_late_arriving_policy in {"ignore", "reject"}
        and not contract.write.scd2_sequence_by
    ):
        blockers.append(
            {
                "code": "MISSING_SCD2_SEQUENCE",
                "message": "historical late-arriving policy ignore/reject requires scd2_sequence_by.",
            }
        )
    if contract.write.mode == "snapshot_soft_delete" and not _source_declares_complete_snapshot(contract):
        blockers.append(
            {
                "code": "MISSING_SOURCE_COMPLETE",
                "message": "snapshot_reconcile_soft_delete requires source.read.source_complete=true or source.read.full_snapshot=true.",
            }
        )
    return blockers


def _draft_sql(contract: SemanticContract, env: GCPEnvironment, source_columns: tuple[str, ...]) -> dict[str, str]:
    mode = contract.write.mode
    if mode == "scd1_hash_diff":
        return _hash_diff_sql(contract, env, source_columns)
    if mode == "scd2_historical":
        return _historical_sql(contract, env, source_columns)
    if mode == "snapshot_soft_delete":
        return _snapshot_sql(contract, env, source_columns)
    return {}


def _hash_diff_sql(contract: SemanticContract, env: GCPEnvironment, source_columns: tuple[str, ...]) -> dict[str, str]:
    hash_inputs = resolved_hash_input_columns(contract, source_columns=source_columns)
    source_sql = _source_sql(contract, env)
    staged = "__cf_hash_diff_stage"
    row_hash = _row_hash_expression(hash_inputs)
    target = target_table(contract, env)
    merge_keys = set(contract.write.merge_keys)
    update_columns = [column for column in source_columns if column not in merge_keys]
    all_columns = tuple(dict.fromkeys((*source_columns, "row_hash")))
    return {
        "stage": "\n".join(
            [
                f"CREATE TEMP TABLE {staged} AS",
                "SELECT",
                "  S.*,",
                f"  {row_hash} AS row_hash",
                f"FROM ({source_sql}) AS S;",
            ]
        ),
        "merge": "\n".join(
            [
                f"MERGE {target} AS T",
                f"USING {staged} AS S",
                f"ON {_on_clause(contract.write.merge_keys)}",
                "WHEN MATCHED AND COALESCE(T.row_hash, '') != COALESCE(S.row_hash, '') THEN",
                "  UPDATE SET "
                + ", ".join([*(f"{identifier(column)} = S.{identifier(column)}" for column in update_columns), "row_hash = S.row_hash"]),
                "WHEN NOT MATCHED THEN",
                f"  INSERT ({_column_csv(all_columns)}) VALUES ({_source_column_csv(all_columns)});",
            ]
        ),
        "readback": f"SELECT COUNT(*) AS changed_rows FROM {staged};",
    }


def _historical_sql(contract: SemanticContract, env: GCPEnvironment, source_columns: tuple[str, ...]) -> dict[str, str]:
    spec = scd2_stage_spec_from_contract(contract, source_columns=source_columns)
    source_sql = _source_sql(contract, env)
    staged = "__cf_scd2_stage"
    target = target_table(contract, env)
    row_hash = _row_hash_expression(spec.change_columns)
    effective_from = f"S.{identifier(spec.effective_from_column)}" if spec.effective_from_column else "CURRENT_TIMESTAMP()"
    apply_as_delete = _apply_as_delete_expression(contract)
    late_sequence = f"S.{identifier(_historical_sequence_column(spec))}" if _historical_sequence_column(spec) else "NULL"
    insert_columns = tuple(dict.fromkeys((*source_columns, "valid_from", "valid_to", "is_current", "row_hash", "changed_columns")))
    insert_values = tuple(
        [
            *(f"S.{identifier(column)}" for column in source_columns),
            "S.valid_from",
            "TIMESTAMP '9999-12-31 23:59:59 UTC'",
            "TRUE",
            "S.row_hash",
            "S.changed_columns",
        ]
    )
    return {
        "stage": "\n".join(
            [
                f"CREATE TEMP TABLE {staged} AS",
                "SELECT",
                "  S.*,",
                f"  {effective_from} AS valid_from,",
                f"  {late_sequence} AS __cf_sequence_by,",
                f"  {apply_as_delete} AS apply_as_delete,",
                f"  {row_hash} AS row_hash,",
                f"  IF({apply_as_delete}, ['DELETE'], [{', '.join(_sql_string(column) for column in spec.change_columns)}]) AS changed_columns",
                f"FROM ({source_sql}) AS S;",
            ]
        ),
        **(
            {
                "late_arriving_guard": _historical_late_arriving_preflight_sql(
                    contract,
                    env,
                    source=f"`{staged}`",
                    source_alias="S",
                    target=target,
                    include_semicolon=True,
                )
            }
            if spec.late_arriving_policy == "reject"
            else {}
        ),
        "expire_current": "\n".join(
            [
                f"UPDATE {target} AS T",
                "SET valid_to = TIMESTAMP_SUB(S.valid_from, INTERVAL 1 MICROSECOND),",
                "    is_current = FALSE,",
                "    changed_columns = IF(S.apply_as_delete, ['DELETE'], T.changed_columns)",
                f"FROM {staged} AS S",
                f"WHERE {_where_on_clause(contract.write.merge_keys)}",
                "  AND T.is_current = TRUE",
                "  AND (S.apply_as_delete OR COALESCE(T.row_hash, '') != COALESCE(S.row_hash, ''))"
                + _late_arriving_where_clause(spec)
                + ";",
            ]
        ),
        "insert_current": "\n".join(
            [
                f"INSERT INTO {target} ({_column_csv(insert_columns)})",
                "SELECT",
                "  " + ", ".join(insert_values),
                f"FROM {staged} AS S",
                f"LEFT JOIN {target} AS T",
                f"ON {_where_on_clause(contract.write.merge_keys)} AND T.is_current = TRUE",
                "WHERE NOT S.apply_as_delete",
                "  AND (T.row_hash IS NULL OR COALESCE(T.row_hash, '') != COALESCE(S.row_hash, ''))"
                + _late_arriving_where_clause(spec)
                + ";",
            ]
        ),
        "readback": f"SELECT COUNTIF(is_current) AS current_rows, COUNT(*) AS history_rows FROM {target};",
    }


def _snapshot_sql(contract: SemanticContract, env: GCPEnvironment, source_columns: tuple[str, ...]) -> dict[str, str]:
    source_sql = _source_sql(contract, env)
    staged = "__cf_snapshot_stage"
    target = target_table(contract, env)
    row_hash = _row_hash_expression(tuple(column for column in source_columns if column not in set(contract.write.merge_keys)))
    all_columns = tuple(dict.fromkeys((*source_columns, "is_active", "deleted_at", "row_hash")))
    update_columns = [column for column in source_columns if column not in set(contract.write.merge_keys)]
    return {
        "stage": "\n".join(
            [
                f"CREATE TEMP TABLE {staged} AS",
                "SELECT",
                "  S.*,",
                "  TRUE AS is_active,",
                "  CAST(NULL AS TIMESTAMP) AS deleted_at,",
                f"  {row_hash} AS row_hash",
                f"FROM ({source_sql}) AS S;",
            ]
        ),
        "merge": "\n".join(
            [
                f"MERGE {target} AS T",
                f"USING {staged} AS S",
                f"ON {_on_clause(contract.write.merge_keys)}",
                "WHEN MATCHED AND (T.is_active = FALSE OR COALESCE(T.row_hash, '') != COALESCE(S.row_hash, '')) THEN",
                "  UPDATE SET "
                + ", ".join([*(f"{identifier(column)} = S.{identifier(column)}" for column in update_columns), "is_active = TRUE", "deleted_at = NULL", "row_hash = S.row_hash"]),
                "WHEN NOT MATCHED THEN",
                f"  INSERT ({_column_csv(all_columns)}) VALUES ({_source_column_csv(all_columns)})",
                "WHEN NOT MATCHED BY SOURCE AND T.is_active = TRUE THEN",
                "  UPDATE SET is_active = FALSE, deleted_at = CURRENT_TIMESTAMP();",
            ]
        ),
        "readback": f"SELECT COUNTIF(NOT is_active) AS soft_deleted_rows, COUNT(*) AS total_rows FROM {target};",
    }


def _promotion_evidence_required(mode: str) -> list[str]:
    common = [
        "BigQuery job statistics for affected rows, bytes processed and slot milliseconds.",
        "Run, quality and lineage evidence rows linked to the same ContractForge run id.",
        "Cross-adapter replay proving no silent fallback to append, overwrite or current-state upsert.",
    ]
    if mode == "scd1_hash_diff":
        return [
            "Initial load, no-change replay, changed-row replay, duplicate-key failure and null-key failure.",
            "Hash expression parity for casts, null sentinels, delimiters, ordering and generated-column exclusions.",
            *common,
        ]
    if mode == "scd2_historical":
        return [
            "Initial load, changed-row wave, no-change replay, late-arriving policy and validity-window closure.",
            "Current-row uniqueness and historical row overlap checks.",
            *common,
        ]
    return [
        "Complete-source declaration proof, missing-key tombstone behavior and idempotent replay.",
        "Soft-delete readback for active and inactive rows.",
        *common,
    ]


def _hash_diff_executable_sql(contract: SemanticContract, env: GCPEnvironment, source_columns: tuple[str, ...]) -> str:
    source = _hashed_source_subquery(contract, env, resolved_hash_input_columns(contract, source_columns=source_columns))
    target = target_table(contract, env)
    merge_keys = set(contract.write.merge_keys)
    update_columns = [column for column in source_columns if column not in merge_keys]
    all_columns = tuple(dict.fromkeys((*source_columns, "row_hash")))
    return "\n".join(
        [
            _source_key_preflight_sql(contract, env),
            f"MERGE {target} AS T",
            f"USING {source} AS S",
            f"ON {_on_clause(contract.write.merge_keys)}",
            "WHEN MATCHED AND COALESCE(T.row_hash, '') != COALESCE(S.row_hash, '') THEN",
            "  UPDATE SET "
            + ", ".join([*(f"{identifier(column)} = S.{identifier(column)}" for column in update_columns), "row_hash = S.row_hash"]),
            "WHEN NOT MATCHED THEN",
            f"  INSERT ({_column_csv(all_columns)}) VALUES ({_source_column_csv(all_columns)});",
            "",
        ]
    )


def _historical_executable_sql(contract: SemanticContract, env: GCPEnvironment, source_columns: tuple[str, ...]) -> str:
    spec = scd2_stage_spec_from_contract(contract, source_columns=source_columns)
    source = _historical_source_subquery(contract, env, spec)
    target = target_table(contract, env)
    insert_columns = tuple(dict.fromkeys((*source_columns, "valid_from", "valid_to", "is_current", "row_hash", "changed_columns")))
    insert_values = tuple(
        [
            *(f"S.{identifier(column)}" for column in source_columns),
            "S.valid_from",
            "TIMESTAMP '9999-12-31 23:59:59 UTC'",
            "TRUE",
            "S.row_hash",
            "S.changed_columns",
        ]
    )
    return "\n\n".join(
        [
            _source_key_preflight_sql(contract, env),
            _historical_late_arriving_preflight_sql(contract, env, source=source, source_alias="S", target=target),
            "\n".join(
                [
                    f"UPDATE {target} AS T",
                    "SET valid_to = TIMESTAMP_SUB(S.valid_from, INTERVAL 1 MICROSECOND),",
                    "    is_current = FALSE,",
                    "    changed_columns = IF(S.apply_as_delete, ['DELETE'], T.changed_columns)",
                    f"FROM {source} AS S",
                    f"WHERE {_where_on_clause(contract.write.merge_keys)}",
                    "  AND T.is_current = TRUE",
                    "  AND (S.apply_as_delete OR COALESCE(T.row_hash, '') != COALESCE(S.row_hash, ''))"
                    + _late_arriving_where_clause(spec)
                    + ";",
                ]
            ),
            "\n".join(
                [
                    f"INSERT INTO {target} ({_column_csv(insert_columns)})",
                    "SELECT",
                    "  " + ", ".join(insert_values),
                    f"FROM {source} AS S",
                    f"LEFT JOIN {target} AS T",
                    f"ON {_where_on_clause(contract.write.merge_keys)} AND T.is_current = TRUE",
                    "WHERE NOT S.apply_as_delete",
                    "  AND (T.row_hash IS NULL OR COALESCE(T.row_hash, '') != COALESCE(S.row_hash, ''))"
                    + _late_arriving_where_clause(spec)
                    + ";",
                    "",
                ]
            ),
        ]
    )


def _snapshot_executable_sql(contract: SemanticContract, env: GCPEnvironment, source_columns: tuple[str, ...]) -> str:
    hash_inputs = tuple(column for column in source_columns if column not in set(contract.write.merge_keys))
    source = _snapshot_source_subquery(contract, env, hash_inputs)
    target = target_table(contract, env)
    all_columns = tuple(dict.fromkeys((*source_columns, "is_active", "deleted_at", "row_hash")))
    update_columns = [column for column in source_columns if column not in set(contract.write.merge_keys)]
    return "\n".join(
        [
            _source_key_preflight_sql(contract, env),
            f"MERGE {target} AS T",
            f"USING {source} AS S",
            f"ON {_on_clause(contract.write.merge_keys)}",
            "WHEN MATCHED AND (T.is_active = FALSE OR COALESCE(T.row_hash, '') != COALESCE(S.row_hash, '')) THEN",
            "  UPDATE SET "
            + ", ".join(
                [
                    *(f"{identifier(column)} = S.{identifier(column)}" for column in update_columns),
                    "is_active = TRUE",
                    "deleted_at = NULL",
                    "row_hash = S.row_hash",
                ]
            ),
            "WHEN NOT MATCHED THEN",
            f"  INSERT ({_column_csv(all_columns)}) VALUES ({_source_column_csv(all_columns)})",
            "WHEN NOT MATCHED BY SOURCE AND T.is_active = TRUE THEN",
            "  UPDATE SET is_active = FALSE, deleted_at = CURRENT_TIMESTAMP();",
            "",
        ]
    )


def _hashed_source_subquery(contract: SemanticContract, env: GCPEnvironment, hash_inputs: tuple[str, ...]) -> str:
    source_sql = _source_sql(contract, env)
    return "\n".join(
        [
            "(",
            "  SELECT",
            "    S.*,",
            f"    {_row_hash_expression(hash_inputs)} AS row_hash",
            f"  FROM ({source_sql}) AS S",
            ")",
        ]
    )


def _historical_source_subquery(
    contract: SemanticContract,
    env: GCPEnvironment,
    spec: Any,
) -> str:
    source_sql = _source_sql(contract, env)
    effective_from = f"S.{identifier(spec.effective_from_column)}" if spec.effective_from_column else "CURRENT_TIMESTAMP()"
    sequence_column = _historical_sequence_column(spec)
    late_sequence = f"S.{identifier(sequence_column)}" if sequence_column else "NULL"
    apply_as_delete = _apply_as_delete_expression(contract)
    return "\n".join(
        [
            "(",
            "  SELECT",
            "    S.*,",
            f"    {effective_from} AS valid_from,",
            f"    {late_sequence} AS __cf_sequence_by,",
            f"    {apply_as_delete} AS apply_as_delete,",
            f"    {_row_hash_expression(spec.change_columns)} AS row_hash,",
            f"    IF({apply_as_delete}, ['DELETE'], [{', '.join(_sql_string(column) for column in spec.change_columns)}]) AS changed_columns",
            f"  FROM ({source_sql}) AS S",
            ")",
        ]
    )


def _historical_late_arriving_preflight_sql(
    contract: SemanticContract,
    env: GCPEnvironment,
    *,
    source: str | None = None,
    source_alias: str = "S",
    target: str | None = None,
    include_semicolon: bool = True,
) -> str:
    spec = scd2_stage_spec_from_contract(contract, source_columns=_source_columns(contract))
    if spec.late_arriving_policy != "reject":
        return ""
    if not _historical_sequence_column(spec):
        return ""
    source_ref = source or _historical_source_subquery(contract, env, spec)
    target_ref = target or target_table(contract, env)
    statement = "\n".join(
        [
            "SELECT CAST('CONTRACTFORGE_LATE_ARRIVING_HISTORICAL' AS INT64) AS contractforge_error",
            f"FROM {source_ref} AS {source_alias}",
            f"JOIN {target_ref} AS T",
            f"ON {_where_on_clause(contract.write.merge_keys)} AND T.is_current = TRUE",
            f"WHERE {_late_arriving_mutation_condition(source_alias, 'T', spec)}",
            f"  AND ({source_alias}.apply_as_delete OR COALESCE(T.row_hash, '') != COALESCE({source_alias}.row_hash, ''))",
            "LIMIT 1",
        ]
    )
    return statement + (";" if include_semicolon else "")


def _historical_sequence_column(spec: Any) -> str | None:
    return spec.sequence_by


def _apply_as_delete_expression(contract: SemanticContract) -> str:
    expression = (contract.write.scd2_apply_as_deletes or "").strip()
    if not expression:
        return "FALSE"
    return f"COALESCE(CAST(({expression}) AS BOOL), FALSE)"


def _late_arriving_where_clause(spec: Any) -> str:
    if spec.late_arriving_policy == "apply" or not _historical_sequence_column(spec):
        return ""
    if spec.late_arriving_policy not in {"ignore", "reject"}:
        raise ValueError("scd2_late_arriving_policy must be one of apply, ignore, reject")
    return f"\n  AND NOT ({_late_arriving_mutation_condition('S', 'T', spec)})"


def _late_arriving_mutation_condition(source_alias: str, target_alias: str, spec: Any) -> str:
    target_sequence = f"{target_alias}.{identifier(spec.sequence_by)}" if spec.sequence_by else f"{target_alias}.valid_from"
    return (
        f"{target_sequence} IS NOT NULL "
        f"AND ({source_alias}.__cf_sequence_by IS NULL OR {source_alias}.__cf_sequence_by <= {target_sequence})"
    )


def _snapshot_source_subquery(contract: SemanticContract, env: GCPEnvironment, hash_inputs: tuple[str, ...]) -> str:
    source_sql = _source_sql(contract, env)
    return "\n".join(
        [
            "(",
            "  SELECT",
            "    S.*,",
            "    TRUE AS is_active,",
            "    CAST(NULL AS TIMESTAMP) AS deleted_at,",
            f"    {_row_hash_expression(hash_inputs)} AS row_hash",
            f"  FROM ({source_sql}) AS S",
            ")",
        ]
    )


def _source_key_preflight_sql(contract: SemanticContract, env: GCPEnvironment) -> str:
    source_sql = _source_sql(contract, env)
    key_columns = tuple(contract.write.merge_keys)
    key_csv = ", ".join(f"S.{identifier(key)}" for key in key_columns)
    null_predicate = " OR ".join(f"S.{identifier(key)} IS NULL" for key in key_columns)
    return "\n\n".join(
        [
            "\n".join(
                [
                    "SELECT CAST('CONTRACTFORGE_NULL_MERGE_KEY' AS INT64) AS contractforge_error",
                    f"FROM ({source_sql}) AS S",
                    f"WHERE {null_predicate}",
                    "LIMIT 1;",
                ]
            ),
            "\n".join(
                [
                    "SELECT CAST('CONTRACTFORGE_DUPLICATE_MERGE_KEYS' AS INT64) AS contractforge_error",
                    "FROM (",
                    "  SELECT",
                    f"    {key_csv}",
                    f"  FROM ({source_sql}) AS S",
                    f"  GROUP BY {key_csv}",
                    "  HAVING COUNT(*) > 1",
                    "  LIMIT 1",
                    ") AS duplicate_merge_keys",
                    "LIMIT 1;",
                ]
            ),
            "",
        ]
    )


def _source_declares_complete_snapshot(contract: SemanticContract) -> bool:
    source = contract.source.raw or {}
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    return bool(read.get("source_complete") or read.get("full_snapshot") or source.get("source_complete"))


def _source_columns(contract: SemanticContract) -> tuple[str, ...]:
    metadata = contract.operations.metadata if contract.operations and isinstance(contract.operations.metadata, dict) else {}
    source = contract.source.raw or {}
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    for value in (metadata.get("select_columns"), read.get("columns"), read.get("select_columns"), source.get("columns")):
        columns = _column_list(value)
        if columns:
            return tuple(dict.fromkeys(columns))
    return ()


def _column_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        columns: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("column") or item.get("field") or "").strip()
                if name:
                    columns.append(name)
            else:
                name = str(item).strip()
                if name:
                    columns.append(name)
        return columns
    return []


def _source_sql(contract: SemanticContract, env: GCPEnvironment) -> str:
    source = contract.source.raw or {}
    source_type = str(source.get("type") or source.get("connector") or "").strip().lower()
    if source_type == "sql":
        options = source.get("options") if isinstance(source.get("options"), dict) else {}
        return str(source.get("query") or options.get("query") or "SELECT * FROM source_query")
    if source_type in {"table", "view", "iceberg_table"}:
        table = source.get("table") or source.get("table_ref") or source.get("ref") or contract.source.location
        return f"SELECT * FROM {quote_table_ref(str(table), env)}"
    return f"SELECT * FROM {staging_table(contract, env)}"


def _row_hash_expression(columns: tuple[str, ...]) -> str:
    parts = ", ".join(f"COALESCE(CAST(S.{identifier(column)} AS STRING), {_sql_value_expression(HASH_NULL_SENTINEL)})" for column in columns)
    return f"TO_HEX(SHA256(ARRAY_TO_STRING([{parts}], {_sql_value_expression(HASH_DELIMITER)})))"


def _sql_value_expression(value: str) -> str:
    if any(ord(char) < 32 for char in value):
        return f"CODE_POINTS_TO_STRING([{', '.join(str(ord(char)) for char in value)}])"
    return _sql_string(value)


def _on_clause(keys: tuple[str, ...]) -> str:
    return " AND ".join(f"T.{identifier(key)} = S.{identifier(key)}" for key in keys)


def _where_on_clause(keys: tuple[str, ...]) -> str:
    return " AND ".join(f"T.{identifier(key)} = S.{identifier(key)}" for key in keys)


def _column_csv(columns: tuple[str, ...]) -> str:
    return ", ".join(identifier(column) for column in columns)


def _source_column_csv(columns: tuple[str, ...]) -> str:
    return ", ".join(f"S.{identifier(column)}" for column in columns)


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
