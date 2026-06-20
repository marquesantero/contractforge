"""PySpark deduplication helpers for portable transform intent."""

from __future__ import annotations

import re
from typing import Any


def apply_transform_deduplicate(df: Any, deduplicate: object) -> Any:
    if not isinstance(deduplicate, dict):
        return df
    from pyspark.sql import Window, functions as F

    keys = deduplicate.get("keys")
    key_columns = [str(keys)] if isinstance(keys, str) else [str(key) for key in keys or ()]
    if not key_columns:
        raise ValueError("transform.deduplicate.keys is required")
    _validate_columns(df, {column: True for column in key_columns}, "transform.deduplicate.keys")
    window = Window.partitionBy(*key_columns).orderBy(*_deduplicate_order_columns(deduplicate.get("order_by"), F))
    return df.withColumn("__cf_row_number", F.row_number().over(window)).filter(F.col("__cf_row_number") == 1).drop(
        "__cf_row_number"
    )


def _deduplicate_order_columns(order_by: object, functions: Any) -> list[Any]:
    if isinstance(order_by, str):
        return _deduplicate_order_columns_from_string(order_by, functions)
    order_columns = []
    for item in order_by or ():
        if not isinstance(item, dict):
            continue
        order_columns.append(
            _deduplicate_order_column(
                functions.col(str(item["column"])),
                direction=str(item.get("direction", "desc")).lower(),
                nulls=str(item.get("nulls") or "").lower(),
            )
        )
    if not order_columns:
        raise ValueError("transform.deduplicate.order_by is required")
    return order_columns


def _deduplicate_order_columns_from_string(order_by: str, functions: Any) -> list[Any]:
    order_columns = []
    for clause in (item.strip() for item in order_by.split(",")):
        if not clause:
            continue
        parsed = re.match(
            r"^`?(?P<column>[A-Za-z_][A-Za-z0-9_]*)`?(?:\s+(?P<direction>ASC|DESC))?(?:\s+NULLS\s+(?P<nulls>FIRST|LAST))?$",
            clause,
            flags=re.IGNORECASE,
        )
        if parsed is None:
            order_columns.append(functions.expr(clause))
            continue
        order_columns.append(
            _deduplicate_order_column(
                functions.col(parsed.group("column")),
                direction=(parsed.group("direction") or "desc").lower(),
                nulls=(parsed.group("nulls") or "").lower(),
            )
        )
    if not order_columns:
        raise ValueError("transform.deduplicate.order_by is required")
    return order_columns


def _deduplicate_order_column(column: Any, *, direction: str, nulls: str) -> Any:
    if direction == "asc" and nulls == "first":
        return column.asc_nulls_first()
    if direction == "asc" and nulls == "last":
        return column.asc_nulls_last()
    if direction == "asc":
        return column.asc()
    if nulls == "first":
        return column.desc_nulls_first()
    if nulls == "last":
        return column.desc_nulls_last()
    return column.desc()


def _validate_columns(df: Any, columns: dict[str, Any], context: str) -> None:
    available = set(getattr(df, "columns", ()) or ())
    missing = sorted(str(column) for column in columns if str(column) not in available)
    if missing:
        raise ValueError(f"{context} references missing columns: {missing}")
