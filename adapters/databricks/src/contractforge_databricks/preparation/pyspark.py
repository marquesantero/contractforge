"""Optional PySpark staging helpers.

Imports stay inside functions so the package can be imported without PySpark.
"""

from __future__ import annotations

from typing import Any

from contractforge_core.config import CONTROL_COLUMNS
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.preparation.deduplicate import apply_transform_deduplicate
from contractforge_databricks.preparation.encoding import apply_encoding_fix


def create_or_replace_temp_view(df: Any, name: str) -> str:
    if not name or not name.strip():
        raise ValueError("temp view name must not be empty")
    df.createOrReplaceTempView(name)
    return name


def apply_transform(df: Any, transform: dict[str, Any] | None) -> Any:
    """Apply portable transform intent with PySpark DataFrame operations."""

    if not transform:
        return df
    df = apply_transform_cast(df, _dict(transform.get("cast")))
    df = apply_transform_standardize(df, _dict(transform.get("standardize")))
    df = apply_transform_derive(df, _dict(transform.get("derive")))
    df = apply_transform_composite_keys(df, _dict(transform.get("composite_keys")))
    return apply_transform_deduplicate(df, transform.get("deduplicate"))


def apply_contract_preparation(
    df: Any,
    contract: SemanticContract,
    *,
    watermark_column: str | None = None,
    watermark_previous: str | None = None,
) -> Any:
    """Apply portable pre-write preparation declared in the core contract."""

    metadata = _contract_metadata(contract)
    select_columns = _string_list(metadata.get("select_columns"))
    if select_columns:
        _validate_columns(df, {column: True for column in select_columns}, "select_columns")
        df = df.select(*select_columns)
    column_mapping = _dict(metadata.get("column_mapping"))
    if column_mapping:
        _validate_column_mapping(df, column_mapping)
        for source_col, target_col in column_mapping.items():
            df = df.withColumnRenamed(str(source_col), str(target_col))
    if contract.shape:
        from contractforge_databricks.preparation.shape import apply_shape

        df = apply_shape(df, contract.shape.raw, layer=contract.target.layer)
    transform = contract.transform.raw if contract.transform else {}
    df = apply_transform_cast(df, _dict(transform.get("cast")))
    df = apply_transform_standardize(df, _dict(transform.get("standardize")))
    df = apply_transform_derive(df, _dict(transform.get("derive")))
    filter_expression = metadata.get("filter_expression")
    if filter_expression:
        from pyspark.sql import functions as F

        df = df.where(F.expr(str(filter_expression)))
    df = apply_transform_composite_keys(df, _dict(transform.get("composite_keys")))
    df = _apply_watermark_filter(df, watermark_column, watermark_previous)
    df = apply_transform_deduplicate(df, transform.get("deduplicate"))
    return apply_encoding_fix(df, contract)


def apply_transform_cast(df: Any, casts: dict[str, Any]) -> Any:
    if not casts:
        return df
    from pyspark.sql import functions as F

    _validate_columns(df, casts, "transform.cast")
    for column_name, data_type in casts.items():
        df = df.withColumn(str(column_name), F.col(str(column_name)).cast(str(data_type)))
    return df


def apply_transform_derive(df: Any, expressions: dict[str, Any]) -> Any:
    if not expressions:
        return df
    from pyspark.sql import functions as F

    for column_name, expression in expressions.items():
        df = df.withColumn(str(column_name), F.expr(str(expression)))
    return df


def apply_transform_composite_keys(df: Any, composite_keys: dict[str, Any]) -> Any:
    if not composite_keys:
        return df
    from pyspark.sql import functions as F

    for key_name, source_columns in composite_keys.items():
        columns = [source_columns] if isinstance(source_columns, str) else list(source_columns or ())
        _validate_columns(df, {str(column): True for column in columns}, f"transform.composite_keys.{key_name}")
        parts = [F.coalesce(F.col(str(column)).cast("string"), F.lit("")) for column in columns]
        df = df.withColumn(str(key_name), F.concat_ws("|", *parts))
    return df


def apply_transform_standardize(df: Any, standardize: dict[str, Any]) -> Any:
    if not standardize:
        return df
    from pyspark.sql import functions as F

    _validate_columns(df, standardize, "transform.standardize")
    for column_name, config in standardize.items():
        column = F.col(str(column_name))
        if config.get("normalize_whitespace"):
            column = F.regexp_replace(column, r"\s+", " ")
        if config.get("trim"):
            column = F.trim(column)
        if config.get("lower"):
            column = F.lower(column)
        if config.get("upper"):
            column = F.upper(column)
        if config.get("empty_as_null"):
            column = F.when(column == "", F.lit(None)).otherwise(column)
        df = df.withColumn(str(column_name), column)
    return df


def _validate_columns(df: Any, columns: dict[str, Any], context: str) -> None:
    available = set(getattr(df, "columns", ()) or ())
    missing = sorted(str(column) for column in columns if str(column) not in available)
    if missing:
        raise ValueError(f"{context} references missing columns: {missing}")


def _validate_column_mapping(df: Any, mapping: dict[str, Any]) -> None:
    _validate_columns(df, mapping, "column_mapping")
    existing = set(getattr(df, "columns", ()) or ())
    targets = [str(target) for target in mapping.values()]
    duplicates = sorted({target for target in targets if targets.count(target) > 1})
    if duplicates:
        raise ValueError(f"column_mapping has duplicate targets: {duplicates}")
    reserved_targets = sorted(set(targets) & CONTROL_COLUMNS)
    if reserved_targets:
        raise ValueError(f"column_mapping cannot produce reserved control columns: {reserved_targets}")
    collisions = sorted(
        target
        for source, target in ((str(source), str(target)) for source, target in mapping.items())
        if target in existing and target != source
    )
    if collisions:
        raise ValueError(f"column_mapping would collide with existing columns: {collisions}")


def _apply_watermark_filter(df: Any, watermark_column: str | None, watermark_value: str | None) -> Any:
    if not watermark_column or not watermark_value:
        return df
    from contractforge_databricks.watermark import render_watermark_filter_predicate

    columns = tuple(part for part in watermark_column.split("|") if part)
    _validate_columns(df, {column: True for column in columns}, "watermark_columns")
    return df.where(render_watermark_filter_predicate(columns=columns, watermark_value=watermark_value))


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _contract_metadata(contract: SemanticContract) -> dict[str, Any]:
    return dict(contract.operations.metadata or {}) if contract.operations and contract.operations.metadata else {}


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item) for item in value or ()]
