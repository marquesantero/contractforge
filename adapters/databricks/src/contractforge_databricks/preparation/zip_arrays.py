"""PySpark execution for shape.zip_arrays."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.preparation.shape_validation import as_dict, data_type_at_path, path_col, validate_columns


def apply_zip_arrays(df: Any, configs: list[dict[str, Any]]) -> Any:
    """Zip parallel arrays and rename struct fields according to the contract."""

    from pyspark.sql import functions as F
    from pyspark.sql.types import ArrayType

    aliases = set(getattr(df, "columns", ()) or ())
    for config_idx, config in enumerate(configs):
        alias = str(config["alias"])
        if alias in aliases:
            raise ValueError(f"shape.zip_arrays would collide with existing column: {alias}")
        columns = as_dict(config.get("columns"))
        if not columns:
            raise ValueError("shape.zip_arrays.columns is required")
        validate_columns(df, {path: True for path in columns}, "shape.zip_arrays")
        temp_columns = []
        for path, field_alias in columns.items():
            data_type = data_type_at_path(getattr(df, "schema", None), path)
            if data_type is not None and not isinstance(data_type, ArrayType):
                raise ValueError(f"shape.zip_arrays.{path} must be array")
            temp = _unique_temp_column(getattr(df, "columns", ()) or (), f"__cf_shape_zip_{config_idx}_{len(temp_columns)}")
            df = df.withColumn(temp, path_col(F, str(path)))
            temp_columns.append((temp, str(field_alias)))

        zipped = F.arrays_zip(*[F.col(temp) for temp, _ in temp_columns])
        renamed = F.transform(
            zipped,
            lambda item: F.struct(*[item.getField(temp).alias(field_alias) for temp, field_alias in temp_columns]),
        )
        df = df.withColumn(alias, renamed).drop(*[temp for temp, _ in temp_columns])
        aliases.add(alias)
    return df


def _unique_temp_column(columns: object, prefix: str) -> str:
    existing = set(columns or ())
    candidate = prefix
    idx = 0
    while candidate in existing:
        idx += 1
        candidate = f"{prefix}_{idx}"
    return candidate
