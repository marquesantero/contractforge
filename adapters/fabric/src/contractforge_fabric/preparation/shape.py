"""Render portable Fabric notebook shape preparation steps."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_fabric.preparation.flatten import flatten_config, render_flatten, render_flatten_helper

_RENDERABLE_SHAPE_KEYS = frozenset({"parse_json", "arrays", "columns", "flatten"})
_IGNORED_SHAPE_KEYS = frozenset({"allow_cardinality_change_on_bronze", "cardinality_policy", "cardinality"})


def can_render_shape(contract: SemanticContract) -> bool:
    shape = shape_payload(contract)
    if not shape:
        return True
    for key, value in shape.items():
        if key in _RENDERABLE_SHAPE_KEYS or key in _IGNORED_SHAPE_KEYS:
            continue
        if value:
            return False
    return all(_can_render_parse_json(config) for config in shape.get("parse_json") or []) and all(
        _can_render_array(config) for config in shape.get("arrays") or []
    )


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
        lines.extend(_arrays(arrays, dataframe_name=dataframe_name))
    columns = _as_dict(shape.get("columns"))
    if columns:
        lines.extend(_columns(columns, dataframe_name=dataframe_name))
    flatten = flatten_config(shape.get("flatten"))
    if flatten.get("enabled"):
        lines.extend(render_flatten(flatten, dataframe_name=dataframe_name))
    return lines


def shape_payload(contract: SemanticContract) -> dict[str, Any]:
    if contract.shape is not None and contract.shape.raw:
        return dict(contract.shape.raw)
    transform = contract.transform.raw if contract.transform else {}
    nested = transform.get("shape") if isinstance(transform, dict) else None
    return dict(nested) if isinstance(nested, dict) else {}


def _parse_json(configs: list[Any], *, dataframe_name: str) -> list[str]:
    lines: list[str] = []
    for config in configs:
        config = _as_dict(config)
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
    config = _as_dict(config)
    if not config.get("column") or not config.get("schema"):
        return False
    cast_input = str(config.get("cast_input") or "").strip().upper()
    return cast_input in {"", "STRING"}


def _arrays(configs: list[Any], *, dataframe_name: str) -> list[str]:
    lines: list[str] = []
    for config in configs:
        config = _as_dict(config)
        path = str(config["path"])
        alias = str(config["alias"])
        function_name = _array_function_name(str(config.get("mode") or "explode_outer"))
        lines.append(f"{dataframe_name} = {dataframe_name}.withColumn({alias!r}, F.{function_name}(F.col({path!r})))")
    lines.append("")
    return lines


def _can_render_array(config: Any) -> bool:
    config = _as_dict(config)
    if not config.get("path") or not config.get("alias"):
        return False
    try:
        _array_function_name(str(config.get("mode") or "explode_outer"))
    except ValueError:
        return False
    return not bool(config.get("allow_cartesian"))


def _array_function_name(mode: str) -> str:
    normalized = mode.strip().casefold()
    if normalized == "explode":
        return "explode"
    if normalized in {"explode_outer", "outer"}:
        return "explode_outer"
    raise ValueError(f"Fabric shape.arrays supports only explode and explode_outer, got: {mode}")


def _columns(columns: dict[str, Any], *, dataframe_name: str) -> list[str]:
    projected: list[str] = []
    for path, config in columns.items():
        path = str(path)
        if isinstance(config, str):
            projected.append(f"F.col({path!r}).alias({config!r})")
            continue
        config = _as_dict(config)
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


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


__all__ = [
    "can_render_shape",
    "render_flatten_helper",
    "render_shape_preparation",
    "shape_payload",
    "shape_requires_flatten",
]
