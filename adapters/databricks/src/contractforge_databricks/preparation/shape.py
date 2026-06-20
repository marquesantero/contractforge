"""Optional PySpark execution for declarative shape intent."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.preparation.shape_validation import (
    CARDINALITY_CHANGING_MODES,
    as_dict,
    as_list,
    data_type_at_path,
    flatten_config,
    is_excluded,
    path_col,
    validate_cardinality_policy,
    validate_cartesian_arrays,
    validate_columns,
)
from contractforge_databricks.preparation.zip_arrays import apply_zip_arrays


def apply_shape(df: Any, shape: dict[str, Any] | None, *, layer: str = "silver") -> Any:
    """Apply portable shape intent with PySpark DataFrame operations."""

    if not shape:
        return df
    validate_cardinality_policy(shape, layer)
    validate_cartesian_arrays(shape)
    df = _apply_parse_json(df, as_list(shape.get("parse_json")))
    df = apply_zip_arrays(df, as_list(shape.get("zip_arrays")))
    df = _apply_arrays(df, as_list(shape.get("arrays")))
    df = _drop_shape_intermediates(df, shape)
    df = _apply_columns(df, as_dict(shape.get("columns")))
    return _apply_flatten(df, shape.get("flatten"))


def _apply_parse_json(df: Any, configs: list[dict[str, Any]]) -> Any:
    from pyspark.sql import functions as F
    from pyspark.sql.types import StringType

    for config in configs:
        column = str(config["column"])
        validate_columns(df, {column: True}, "shape.parse_json")
        cast_input = str(config.get("cast_input") or "").strip().upper()
        source_expr = path_col(F, column)
        if cast_input == "STRING":
            source_expr = source_expr.cast("string")
        elif cast_input:
            raise ValueError(f"shape.parse_json.{column}.cast_input={cast_input!r} is not supported")
        else:
            data_type = data_type_at_path(getattr(df, "schema", None), column)
            if data_type is not None and not isinstance(data_type, StringType):
                raise ValueError(
                    f"shape.parse_json.{column} must be string;"
                    " declare cast_input: STRING to coerce a binary/non-string source column"
                )
        schema = config.get("schema")
        if not schema:
            raise ValueError("shape.parse_json requires schema for runtime execution")
        alias = str(config.get("alias") or column)
        df = df.withColumn(alias, F.from_json(source_expr, str(schema)))
        if config.get("drop_source") and alias != column:
            df = df.drop(column)
    return df


def _apply_arrays(df: Any, arrays: list[dict[str, Any]]) -> Any:
    from pyspark.sql import functions as F
    from pyspark.sql.types import ArrayType

    pending = [config for config in arrays if str(config.get("mode", "keep")) != "keep"]
    while pending:
        progressed = False
        remaining = []
        for config in pending:
            top_level = str(config["path"]).split(".", 1)[0]
            if top_level not in set(getattr(df, "columns", ()) or ()):
                remaining.append(config)
                continue
            df = _apply_array_config(df, config, F, ArrayType)
            progressed = True
        if not progressed:
            unresolved = [str(config["path"]) for config in remaining]
            raise ValueError(f"shape.arrays contains unresolved paths: {unresolved}")
        pending = remaining
    return df


def _apply_array_config(df: Any, config: dict[str, Any], functions: Any, array_type: Any) -> Any:
        mode = str(config.get("mode", "keep"))
        path = str(config["path"])
        data_type = data_type_at_path(getattr(df, "schema", None), path)
        if data_type is not None and not isinstance(data_type, array_type):
            raise ValueError(f"shape.arrays.{path} must be array")
        alias = str(config.get("alias") or path.replace(".", "_"))
        column = path_col(functions, path)
        if mode == "to_json":
            expr = functions.to_json(column)
        elif mode == "size":
            expr = functions.size(column)
        elif mode == "first":
            expr = functions.element_at(column, 1)
        elif mode == "explode":
            expr = functions.explode(column)
        elif mode == "explode_outer":
            expr = functions.explode_outer(column)
        else:
            raise ValueError(f"shape.arrays mode {mode!r} is not supported")
        return df.withColumn(alias, expr)


def _apply_columns(df: Any, columns: dict[str, Any]) -> Any:
    if not columns:
        return df
    from pyspark.sql import functions as F

    projected = []
    for path, config in columns.items():
        if isinstance(config, str):
            alias = config
            expr = path_col(F, str(path))
        else:
            alias = str(config.get("alias") or str(path).replace(".", "_"))
            expr = F.expr(str(config["expression"])) if config.get("expression") else path_col(F, str(path))
            if config.get("cast"):
                expr = expr.cast(str(config["cast"]))
        projected.append(expr.alias(str(alias)))
    return df.select(*projected)


def _apply_flatten(df: Any, flatten: object) -> Any:
    config = flatten_config(flatten)
    if not config["enabled"]:
        return df
    from pyspark.sql.types import StructType
    from pyspark.sql import functions as F

    projections = []
    aliases = set()
    top_level = set(getattr(df, "columns", ()) or ())
    separator = str(config["separator"])
    max_depth = int(config["max_depth"])
    include = set(config["include"])
    exclude = set(config["exclude"])
    for field in getattr(getattr(df, "schema", None), "fields", ()):
        if include and field.name not in include:
            projections.append(path_col(F, field.name).alias(field.name))
            aliases.add(field.name)
            continue
        if is_excluded(field.name, exclude):
            projections.append(path_col(F, field.name).alias(field.name))
            aliases.add(field.name)
            continue
        if isinstance(field.dataType, StructType):
            for path, alias in _struct_leaf_paths(field.dataType, field.name, separator, max_depth=max_depth):
                if is_excluded(path, exclude):
                    continue
                if alias in top_level:
                    continue
                if alias in aliases:
                    raise ValueError(f"shape.flatten would create duplicate column: {alias}")
                projections.append(path_col(F, path).alias(alias))
                aliases.add(alias)
        else:
            if field.name in aliases:
                raise ValueError(f"shape.flatten would create duplicate column: {field.name}")
            projections.append(path_col(F, field.name).alias(field.name))
            aliases.add(field.name)
    return df.select(*projections) if projections else df


def _drop_shape_intermediates(df: Any, shape: dict[str, Any]) -> Any:
    if shape.get("columns"):
        return df
    arrays = as_list(shape.get("arrays"))
    array_paths = [str(item["path"]) for item in arrays]
    zip_aliases = {
        str(config["alias"])
        for config in as_list(shape.get("zip_arrays"))
        if any(path == str(config["alias"]) or path.startswith(f"{config['alias']}.") for path in array_paths)
    }
    exploded_aliases = {
        str(item.get("alias") or str(item["path"]).replace(".", "_"))
        for item in arrays
        if item.get("mode") in CARDINALITY_CHANGING_MODES
        and any(
            path != str(item["path"])
            and (
                path == str(item.get("alias") or str(item["path"]).replace(".", "_"))
                or path.startswith(f"{item.get('alias') or str(item['path']).replace('.', '_')}.")
            )
            for path in array_paths
        )
    }
    to_drop = sorted((zip_aliases | exploded_aliases) & set(getattr(df, "columns", ()) or ()))
    return df.drop(*to_drop) if to_drop else df


def _struct_leaf_paths(struct: Any, prefix: str, separator: str, *, max_depth: int, depth: int = 1) -> list[tuple[str, str]]:
    from pyspark.sql.types import StructType

    leaves = []
    for field in struct.fields:
        path = f"{prefix}.{field.name}"
        if isinstance(field.dataType, StructType) and depth < max_depth:
            leaves.extend(_struct_leaf_paths(field.dataType, path, separator, max_depth=max_depth, depth=depth + 1))
        else:
            leaves.append((path, path.replace(".", separator)))
    return leaves
