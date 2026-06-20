"""PySpark write-mode staging helpers with lazy imports."""

from __future__ import annotations

from typing import Any

from contractforge_core.preparation import SCD2StageSpec, SnapshotStageSpec, resolved_hash_exclude_columns
from contractforge_core.preparation import scd2_stage_spec_from_contract, snapshot_stage_spec_from_contract
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.preparation.hashing import HASH_DELIMITER, HASH_NULL_SENTINEL, ROW_HASH_COLUMN


def with_row_hash(df: Any, columns: tuple[str, ...], *, exclude: tuple[str, ...] = ()) -> Any:
    from pyspark.sql import functions as F

    included = tuple(column for column in columns if column not in set(exclude))
    if not included:
        raise ValueError("row hash requires at least one included column")
    payload = [F.coalesce(F.col(column).cast("string"), F.lit(HASH_NULL_SENTINEL)) for column in included]
    return df.withColumn(ROW_HASH_COLUMN, F.sha2(F.concat_ws(HASH_DELIMITER, *payload), 256))


def prepare_snapshot_stage(df: Any, spec: SnapshotStageSpec) -> Any:
    from pyspark.sql import functions as F

    source_columns = tuple(column for column in spec.source_columns if column not in {"is_active", "deleted_at", "row_hash"})
    staged = with_row_hash(df, source_columns)
    return staged.withColumn(spec.is_active_column, F.lit(True)).withColumn(
        spec.deleted_at_column,
        F.lit(None).cast("timestamp"),
    )


def prepare_scd2_stage(df: Any, spec: SCD2StageSpec) -> Any:
    from pyspark.sql import functions as F

    staged = with_row_hash(df, spec.change_columns)
    if spec.effective_from_column:
        staged = staged.withColumn("valid_from", F.col(spec.effective_from_column).cast("timestamp"))
    else:
        staged = staged.withColumn("valid_from", F.current_timestamp())
    staged = staged.withColumn("valid_to", F.lit(None).cast("timestamp"))
    staged = staged.withColumn("is_current", F.lit(True))
    staged = staged.withColumn("changed_columns", F.lit(None).cast("string"))
    for key in spec.merge_keys:
        staged = staged.withColumn(f"__merge_key_{key}", F.lit(None))
    return staged


def prepare_hash_diff_stage(df: Any, contract: SemanticContract) -> Any:
    if contract.write.mode != "scd1_hash_diff":
        raise ValueError("Hash-diff staging requires mode=scd1_hash_diff")
    source_columns = tuple(str(column) for column in getattr(df, "columns", ()) or ())
    hash_columns = source_columns if contract.write.hash_strategy == "all_columns_except" else contract.write.hash_keys
    return with_row_hash(
        df,
        hash_columns,
        exclude=resolved_hash_exclude_columns(contract),
    )


def apply_write_staging(df: Any, contract: SemanticContract) -> Any:
    source_columns = tuple(str(column) for column in getattr(df, "columns", ()) or ())
    if contract.write.mode == "scd1_hash_diff":
        return prepare_hash_diff_stage(df, contract)
    if contract.write.mode == "scd2_historical":
        return prepare_scd2_stage(df, scd2_stage_spec_from_contract(contract, source_columns=source_columns))
    if contract.write.mode == "snapshot_soft_delete":
        return prepare_snapshot_stage(df, snapshot_stage_spec_from_contract(contract, source_columns=source_columns))
    return df
