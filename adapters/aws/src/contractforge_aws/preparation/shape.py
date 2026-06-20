"""Render AWS Glue shape preparation steps."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_aws.preparation.arrays import (
    arrays_require_functions,
    can_render_arrays,
    render_arrays,
)
from contractforge_aws.preparation.flatten import (
    flatten_config,
    render_flatten,
    render_flatten_helper,
)
from contractforge_aws.preparation.utils import as_dict

_RENDERABLE_SHAPE_KEYS = frozenset({"parse_json", "arrays", "columns", "flatten", "zip_arrays"})
_IGNORED_SHAPE_KEYS = frozenset({"allow_cardinality_change_on_bronze", "cardinality_policy", "cardinality"})

__all__ = [
    "can_render_shape",
    "render_flatten_helper",
    "render_shape_preparation",
    "shape_payload",
    "shape_requires_flatten",
    "shape_requires_functions",
    "transform_payload",
]


def can_render_shape(contract: SemanticContract) -> bool:
    shape = shape_payload(contract)
    if not shape:
        return True
    for key, value in shape.items():
        if key in _RENDERABLE_SHAPE_KEYS or key in _IGNORED_SHAPE_KEYS:
            continue
        if value:
            return False
    if not all(_can_render_parse_json(config) for config in shape.get("parse_json") or []):
        return False
    return can_render_arrays(shape, layer=contract.target.layer)


def shape_requires_functions(contract: SemanticContract) -> bool:
    shape = shape_payload(contract)
    if shape.get("parse_json") or shape.get("columns") or shape.get("zip_arrays"):
        return True
    return arrays_require_functions(shape.get("arrays") or [])


def shape_requires_flatten(contract: SemanticContract) -> bool:
    return bool(flatten_config(shape_payload(contract).get("flatten")).get("enabled"))


def render_shape_preparation(contract: SemanticContract, *, dataframe_name: str = "df") -> list[str]:
    shape = shape_payload(contract)
    lines: list[str] = []
    parse_json = shape.get("parse_json") or []
    if parse_json:
        lines.extend(_parse_json(parse_json, dataframe_name=dataframe_name))
    arrays = shape.get("arrays") or []
    if arrays:
        lines.extend(render_arrays(arrays, dataframe_name=dataframe_name))
    zip_arrays = shape.get("zip_arrays") or []
    if zip_arrays:
        lines.extend(_zip_arrays(zip_arrays, dataframe_name=dataframe_name))
    columns = as_dict(shape.get("columns"))
    if columns:
        lines.extend(_columns(columns, dataframe_name=dataframe_name))
    flatten = flatten_config(shape.get("flatten"))
    if flatten.get("enabled"):
        lines.extend(render_flatten(flatten, dataframe_name=dataframe_name))
    return lines


def shape_payload(contract: SemanticContract) -> dict[str, Any]:
    if contract.shape is not None and contract.shape.raw:
        return dict(contract.shape.raw)
    nested = transform_payload(contract).get("shape")
    return dict(nested) if isinstance(nested, dict) else {}


def transform_payload(contract: SemanticContract) -> dict[str, Any]:
    return dict(contract.transform.raw or {}) if contract.transform else {}


def _parse_json(configs: list[Any], *, dataframe_name: str) -> list[str]:
    lines: list[str] = []
    for config in configs:
        config = as_dict(config)
        column = str(config["column"])
        schema = str(config["schema"])
        alias = str(config.get("alias") or column)
        cast_input = str(config.get("cast_input") or "").strip().upper()
        source_expr = f"F.col({column!r})"
        if cast_input == "STRING":
            source_expr += ".cast('string')"
        lines.append(
            f"{dataframe_name} = {dataframe_name}.withColumn({alias!r}, F.from_json({source_expr}, {schema!r}))"
        )
        if config.get("drop_source") and alias != column:
            lines.append(f"{dataframe_name} = {dataframe_name}.drop({column!r})")
    lines.append("")
    return lines


def _can_render_parse_json(config: Any) -> bool:
    config = as_dict(config)
    if not config.get("column") or not config.get("schema"):
        return False
    cast_input = str(config.get("cast_input") or "").strip().upper()
    return cast_input in {"", "STRING"}


def _zip_arrays(configs: list[Any], *, dataframe_name: str) -> list[str]:
    normalized = [_zip_array_config(config) for config in configs]
    return [
        f"shape_zip_arrays = {normalized!r}",
        "for config_idx, config in enumerate(shape_zip_arrays):",
        "    alias = str(config['alias'])",
        f"    if alias in {dataframe_name}.columns:",
        "        raise ValueError(f'shape.zip_arrays would collide with existing column: {alias}')",
        "    temp_columns = []",
        "    for path, field_alias in config['columns'].items():",
        f"        existing_columns = list({dataframe_name}.columns) + [temp for temp, _field in temp_columns]",
        "        temp_prefix = f'__cf_shape_zip_{config_idx}_{len(temp_columns)}'",
        "        temp = temp_prefix",
        "        temp_idx = 0",
        "        while temp in existing_columns:",
        "            temp_idx += 1",
        "            temp = f'{temp_prefix}_{temp_idx}'",
        f"        {dataframe_name} = {dataframe_name}.withColumn(temp, F.col(str(path)))",
        "        temp_columns.append((temp, str(field_alias)))",
        "    zipped = F.arrays_zip(*[F.col(temp) for temp, _field in temp_columns])",
        "    renamed = F.transform(",
        "        zipped,",
        "        lambda item: F.struct(*[item.getField(temp).alias(field_alias) for temp, field_alias in temp_columns]),",
        "    )",
        f"    {dataframe_name} = {dataframe_name}.withColumn(alias, renamed).drop(*[temp for temp, _field in temp_columns])",
        "",
    ]


def _zip_array_config(config: Any) -> dict[str, Any]:
    config = as_dict(config)
    columns = {str(path): str(alias) for path, alias in as_dict(config.get("columns")).items()}
    if not config.get("alias") or not columns:
        raise ValueError("shape.zip_arrays requires alias and columns")
    return {"alias": str(config["alias"]), "columns": columns}


def _columns(columns: dict[str, Any], *, dataframe_name: str) -> list[str]:
    projected: list[str] = []
    for path, config in columns.items():
        path = str(path)
        if isinstance(config, str):
            projected.append(f"F.col({path!r}).alias({config!r})")
            continue
        config = as_dict(config)
        alias = str(config.get("alias") or path.replace(".", "_"))
        expression = config.get("expression")
        expr = f"F.expr({str(expression)!r})" if expression else f"F.col({path!r})"
        if config.get("cast"):
            expr = f"{expr}.cast({str(config['cast'])!r})"
        projected.append(f"{expr}.alias({alias!r})")
    return [
        f"{dataframe_name} = {dataframe_name}.select(",
        *[f"    {expression}," for expression in projected],
        ")",
        "",
    ]
