"""Platform-neutral staging specifications for write algorithms."""

from __future__ import annotations

from dataclasses import dataclass

from contractforge_core.semantic import SemanticContract

HASH_DELIMITER = "\u001f"
HASH_NULL_SENTINEL = "\u0000"


@dataclass(frozen=True)
class HashDiffStageSpec:
    source_columns: tuple[str, ...]
    hash_keys: tuple[str, ...]
    hash_strategy: str = "explicit"
    hash_exclude_columns: tuple[str, ...] = ()
    row_hash_column: str = "row_hash"


@dataclass(frozen=True)
class SCD2StageSpec:
    insert_columns: tuple[str, ...]
    merge_keys: tuple[str, ...]
    change_columns: tuple[str, ...]
    effective_from_column: str | None = None
    sequence_by: str | None = None
    late_arriving_policy: str = "apply"
    row_hash_column: str = "row_hash"


@dataclass(frozen=True)
class SnapshotStageSpec:
    source_columns: tuple[str, ...]
    merge_keys: tuple[str, ...]
    row_hash_column: str = "row_hash"
    is_active_column: str = "is_active"
    deleted_at_column: str = "deleted_at"


GENERATED_HASH_EXCLUDE_COLUMNS = frozenset(
    {
        "__run_id",
        "changed_columns",
        "deleted_at",
        "ingestion_date",
        "ingestion_sequence",
        "ingestion_ts_utc",
        "is_active",
        "is_current",
        "row_hash",
        "source_loaded_at",
        "source_loaded_at_utc",
        "valid_from",
        "valid_to",
    }
)


def hash_diff_stage_spec_from_contract(
    contract: SemanticContract,
    *,
    source_columns: tuple[str, ...],
) -> HashDiffStageSpec:
    if contract.write.mode != "scd1_hash_diff":
        raise ValueError("Hash-diff staging requires mode=scd1_hash_diff")
    hash_keys = contract.write.hash_keys
    if contract.write.hash_strategy == "all_columns_except":
        hash_keys = tuple(source_columns)
    return HashDiffStageSpec(
        source_columns=source_columns,
        hash_strategy=contract.write.hash_strategy,
        hash_keys=hash_keys,
        hash_exclude_columns=resolved_hash_exclude_columns(contract),
    )


def resolved_hash_input_columns(contract: SemanticContract, *, source_columns: tuple[str, ...]) -> tuple[str, ...]:
    spec = hash_diff_stage_spec_from_contract(contract, source_columns=source_columns)
    excluded = {*contract.write.merge_keys, *spec.hash_exclude_columns}
    return tuple(column for column in spec.hash_keys if column in source_columns and column not in excluded)


def resolved_hash_exclude_columns(contract: SemanticContract) -> tuple[str, ...]:
    generated = set(GENERATED_HASH_EXCLUDE_COLUMNS)
    transform = contract.transform.raw if contract.transform else {}
    generated.update(_map_keys(transform.get("derive")))
    generated.update(_map_keys(transform.get("composite_keys")))
    return tuple(sorted({*contract.write.hash_exclude_columns, *generated}))


def scd2_stage_spec_from_contract(
    contract: SemanticContract,
    *,
    source_columns: tuple[str, ...],
) -> SCD2StageSpec:
    if contract.write.mode != "scd2_historical":
        raise ValueError("SCD2 staging requires mode=scd2_historical")
    excluded = {*contract.write.merge_keys, *contract.write.hash_exclude_columns}
    change_columns = contract.write.scd2_change_columns or tuple(column for column in source_columns if column not in excluded)
    insert_columns = tuple(dict.fromkeys((*source_columns, "valid_from", "valid_to", "is_current", "row_hash", "changed_columns")))
    return SCD2StageSpec(
        insert_columns=insert_columns,
        merge_keys=contract.write.merge_keys,
        change_columns=change_columns,
        effective_from_column=contract.write.scd2_effective_from_column,
        sequence_by=contract.write.scd2_sequence_by,
        late_arriving_policy=contract.write.scd2_late_arriving_policy,
    )


def _map_keys(value: object) -> tuple[str, ...]:
    if not isinstance(value, dict):
        return ()
    return tuple(str(key) for key in value)


def snapshot_stage_spec_from_contract(
    contract: SemanticContract,
    *,
    source_columns: tuple[str, ...],
) -> SnapshotStageSpec:
    if contract.write.mode != "snapshot_soft_delete":
        raise ValueError("Snapshot staging requires mode=snapshot_soft_delete")
    return SnapshotStageSpec(
        source_columns=tuple(dict.fromkeys((*source_columns, "is_active", "deleted_at", "row_hash"))),
        merge_keys=contract.write.merge_keys,
    )
