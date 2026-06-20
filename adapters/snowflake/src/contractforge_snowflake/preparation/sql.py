"""Render Snowflake SQL for portable preparation intent."""

from __future__ import annotations

import re
from typing import Any, Callable

from contractforge_core.config import CONTROL_COLUMNS
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.preparation.registry import (
    SnowflakePreparationContext,
    SnowflakePreparationStep,
    apply_preparation_steps,
)
from contractforge_snowflake.values import dict_mapping as _mapping
from contractforge_snowflake.values import string_list as _as_list


_UNSAFE_SQL_RE = re.compile(r";|--|/\*")


def apply_preparation_sql(contract: SemanticContract, source_sql: str) -> str:
    """Apply the Snowflake-supported shape/transform subset to a source query."""

    return apply_preparation_steps(contract, source_sql, _PREPARATION_STEPS)


def unsupported_preparation_markers(contract: SemanticContract) -> tuple[str, ...]:
    markers: list[str] = []
    for shape_name, shape in _declared_shapes(contract):
        markers.extend(_unsupported_shape_markers(shape_name, shape))
    transform = contract.transform.raw if contract.transform else {}
    if isinstance(transform, dict):
        supported = {"cast", "composite_keys", "derive", "deduplicate", "standardize", "shape"}
        markers.extend(f"transform.{key}" for key in sorted(set(transform) - supported))
    return tuple(markers)


def _apply_metadata_projection(context: SnowflakePreparationContext) -> str:
    metadata = _contract_metadata(context.contract)
    select_columns = _string_list(metadata.get("select_columns"))
    column_mapping = _mapping(metadata.get("column_mapping"))
    if not select_columns and not column_mapping:
        return context.source_sql
    if column_mapping:
        _validate_column_mapping(column_mapping, selected_columns=select_columns)
    if select_columns:
        return _select(columns=_metadata_projection(select_columns, column_mapping), source_sql=context.source_sql)
    return _rename_columns_sql(context.source_sql, column_mapping)


def _apply_shape_columns(context: SnowflakePreparationContext) -> str:
    sql = context.source_sql
    for _shape_name, shape in _declared_shapes(context.contract):
        columns = _mapping(shape.get("columns"))
        if columns:
            sql = _select(columns=_shape_projection(columns), source_sql=sql)
    return sql


def _apply_transform_cast(context: SnowflakePreparationContext) -> str:
    return _apply_transform_renderer(context, "cast")


def _apply_transform_standardize(context: SnowflakePreparationContext) -> str:
    return _apply_transform_renderer(context, "standardize")


def _apply_transform_derive(context: SnowflakePreparationContext) -> str:
    return _apply_transform_renderer(context, "derive")


def _apply_transform_composite_keys(context: SnowflakePreparationContext) -> str:
    return _apply_transform_renderer(context, "composite_keys")


def _apply_transform_deduplicate(context: SnowflakePreparationContext) -> str:
    return _apply_transform_renderer(context, "deduplicate")


def _apply_transform_renderer(context: SnowflakePreparationContext, name: str) -> str:
    transform = context.contract.transform.raw if context.contract.transform else {}
    if not isinstance(transform, dict):
        return context.source_sql
    payload = transform.get(name)
    if not payload:
        return context.source_sql
    if name == "derive":
        return _derive_projection(context.source_sql, payload, known_columns=_known_expression_columns(context.contract))
    return _TRANSFORM_RENDERERS[name](context.source_sql, payload)


def _apply_filter_expression(context: SnowflakePreparationContext) -> str:
    expression = _contract_metadata(context.contract).get("filter_expression")
    if not expression:
        return context.source_sql
    return _filter_sql(context.source_sql, expression, known_columns=_known_expression_columns(context.contract))


def _shape_projection(columns: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_shape_column(path, config) for path, config in columns.items())


def _shape_column(path: str, config: Any) -> str:
    if isinstance(config, str):
        return f"{_path_expression(path)} AS {quote_identifier(config)}"
    data = _mapping(config)
    alias = str(data.get("alias") or str(path).replace(".", "_"))
    expression = _safe_expression(data.get("expression")) if data.get("expression") else _path_expression(path)
    if data.get("cast"):
        expression = f"CAST({expression} AS {str(data['cast']).upper()})"
    return f"{expression} AS {quote_identifier(alias)}"


def _validate_column_mapping(mapping: dict[str, Any], *, selected_columns: list[str]) -> None:
    normalized = {str(source): str(target) for source, target in mapping.items()}
    targets = list(normalized.values())
    duplicate_targets = sorted({target for target in targets if targets.count(target) > 1})
    if duplicate_targets:
        raise ValueError(f"column_mapping has duplicate targets: {duplicate_targets}")
    reserved_targets = sorted(set(targets) & CONTROL_COLUMNS)
    if reserved_targets:
        raise ValueError(f"column_mapping cannot produce reserved control columns: {reserved_targets}")
    selected = set(selected_columns)
    collisions = sorted(target for source, target in normalized.items() if target in selected and target != source)
    if collisions:
        raise ValueError(f"column_mapping would collide with selected columns: {collisions}")


def _metadata_projection(selected_columns: list[str], mapping: dict[str, Any]) -> tuple[str, ...]:
    normalized = {str(source): str(target) for source, target in mapping.items()}
    return tuple(
        f"{quote_identifier(column)} AS {quote_identifier(normalized.get(column, column))}"
        for column in selected_columns
    )


def _rename_columns_sql(source_sql: str, mapping: dict[str, Any]) -> str:
    renamed = ", ".join(
        f"{quote_identifier(str(source))} AS {quote_identifier(str(target))}"
        for source, target in mapping.items()
    )
    return f"SELECT * RENAME ({renamed})\nFROM (\n{source_sql}\n) AS _CF_PREP"


def _cast_projection(source_sql: str, casts: Any) -> str:
    columns = _mapping(casts)
    projection = tuple(f"CAST({quote_identifier(column)} AS {str(data_type).upper()}) AS {quote_identifier(column)}" for column, data_type in columns.items())
    return _select_replace(source_sql, projection)


def _composite_key_projection(source_sql: str, composite_keys: Any) -> str:
    keys = _mapping(composite_keys)
    projection = tuple(
        f"CONCAT_WS('|', {', '.join(quote_identifier(column) for column in _as_list(columns))}) AS {quote_identifier(name)}"
        for name, columns in keys.items()
    )
    return _select_with_star(source_sql, projection)


def _derive_projection(source_sql: str, expressions: Any, *, known_columns: tuple[str, ...] = ()) -> str:
    projection = tuple(
        f"{_safe_expression(expression, known_columns=known_columns)} AS {quote_identifier(column)}"
        for column, expression in _mapping(expressions).items()
    )
    return _select_with_star(source_sql, projection)


def _standardize_projection(source_sql: str, standardize: Any) -> str:
    projection = tuple(
        f"{_standardize_expression(column, _mapping(config))} AS {quote_identifier(column)}"
        for column, config in _mapping(standardize).items()
    )
    return _select_replace(source_sql, projection)


def _deduplicate_sql(source_sql: str, deduplicate: Any) -> str:
    config = _mapping(deduplicate)
    keys = _as_list(config.get("keys"))
    if not keys:
        raise ValueError("transform.deduplicate.keys is required")
    order_by = _deduplicate_order_by(config.get("order_by"))
    partition = ", ".join(quote_identifier(key) for key in keys)
    return (
        "SELECT * FROM (\n"
        f"{source_sql}\n"
        ") AS _CF_DEDUP\n"
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {order_by}) = 1"
    )


def _filter_sql(source_sql: str, expression: Any, *, known_columns: tuple[str, ...] = ()) -> str:
    return f"SELECT *\nFROM (\n{source_sql}\n) AS _CF_FILTERED\nWHERE {_safe_expression(expression, known_columns=known_columns)}"


def _standardize_expression(column: str, config: dict[str, Any]) -> str:
    expr = quote_identifier(column)
    operations = (
        ("trim", lambda value: f"TRIM({value})"),
        ("lower", lambda value: f"LOWER({value})"),
        ("upper", lambda value: f"UPPER({value})"),
        ("normalize_whitespace", lambda value: f"REGEXP_REPLACE({value}, '\\\\s+', ' ')"),
        ("empty_as_null", lambda value: f"NULLIF({value}, '')"),
    )
    for key, apply in operations:
        if config.get(key):
            expr = apply(expr)
    return expr


def _deduplicate_order_by(value: Any) -> str:
    if isinstance(value, str):
        return _safe_expression(value)
    items = value if isinstance(value, list) else []
    rendered = tuple(_deduplicate_order_item(_mapping(item)) for item in items)
    if not rendered:
        raise ValueError("transform.deduplicate.order_by is required")
    return ", ".join(rendered)


def _deduplicate_order_item(item: dict[str, Any]) -> str:
    column = item.get("column")
    if not column:
        raise ValueError("transform.deduplicate.order_by.column is required")
    direction = str(item.get("direction") or "desc").upper()
    if direction not in {"ASC", "DESC"}:
        raise ValueError("transform.deduplicate.order_by.direction must be asc or desc")
    nulls = str(item.get("nulls") or "").upper()
    nulls_clause = f" NULLS {nulls}" if nulls in {"FIRST", "LAST"} else ""
    return f"{quote_identifier(column)} {direction}{nulls_clause}"


def _select_with_star(source_sql: str, projection: tuple[str, ...]) -> str:
    if not projection:
        return source_sql
    return _select(columns=("*", *projection), source_sql=source_sql)


def _select_replace(source_sql: str, projection: tuple[str, ...]) -> str:
    if not projection:
        return source_sql
    return "SELECT * REPLACE (" + ", ".join(projection) + ")\nFROM (\n" + source_sql + "\n) AS _CF_PREP"


def _select(*, columns: tuple[str, ...], source_sql: str) -> str:
    return "SELECT " + ", ".join(columns) + "\nFROM (\n" + source_sql + "\n) AS _CF_PREP"


def _declared_shapes(contract: SemanticContract) -> tuple[tuple[str, dict[str, Any]], ...]:
    shapes: list[tuple[str, dict[str, Any]]] = []
    if contract.shape and isinstance(contract.shape.raw, dict):
        shapes.append(("shape", contract.shape.raw))
    transform = contract.transform.raw if contract.transform else {}
    transform_shape = transform.get("shape") if isinstance(transform, dict) else None
    if isinstance(transform_shape, dict):
        shapes.append(("transform.shape", transform_shape))
    return tuple(shapes)


def _contract_metadata(contract: SemanticContract) -> dict[str, Any]:
    return dict(contract.operations.metadata or {}) if contract.operations and contract.operations.metadata else {}


def _known_expression_columns(contract: SemanticContract) -> tuple[str, ...]:
    names: set[str] = set()
    source = contract.source.raw if contract.source.raw else {}
    if isinstance(source, dict):
        options = _mapping(source.get("options"))
        columns = options.get("columns")
        if isinstance(columns, dict):
            names.update(str(name) for name in columns)
        elif isinstance(columns, (list, tuple)):
            names.update(str(name) for name in columns)
    metadata = _contract_metadata(contract)
    names.update(_string_list(metadata.get("select_columns")))
    mapping = _mapping(metadata.get("column_mapping"))
    names.update(str(target) for target in mapping.values())
    transform = contract.transform.raw if contract.transform else {}
    if isinstance(transform, dict):
        names.update(str(name) for name in _mapping(transform.get("cast")))
        names.update(str(name) for name in _mapping(transform.get("standardize")))
        names.update(str(name) for name in _mapping(transform.get("derive")))
        names.update(str(name) for name in _mapping(transform.get("composite_keys")))
    for _shape_name, shape in _declared_shapes(contract):
        for path, config in _mapping(shape.get("columns")).items():
            if isinstance(config, str):
                names.add(config)
                continue
            data = _mapping(config)
            names.add(str(data.get("alias") or str(path).replace(".", "_")))
    return tuple(sorted((name for name in names if name), key=len, reverse=True))


def _unsupported_shape_markers(name: str, shape: dict[str, Any]) -> tuple[str, ...]:
    unsupported = tuple(key for key in ("parse_json", "flatten", "zip_arrays", "arrays") if shape.get(key))
    return tuple(f"{name}.{key}" for key in unsupported)


def _path_expression(path: str) -> str:
    return ".".join(quote_identifier(part) for part in str(path).split(".") if part)


def _safe_expression(value: object, *, known_columns: tuple[str, ...] = ()) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Snowflake preparation expression cannot be empty")
    if _UNSAFE_SQL_RE.search(text):
        raise ValueError("Unsafe Snowflake preparation expression")
    return _quote_known_identifiers(text, known_columns)


def _quote_known_identifiers(expression: str, known_columns: tuple[str, ...]) -> str:
    if not known_columns:
        return expression
    parts = re.split(r"('(?:''|[^'])*')", expression)
    for index in range(0, len(parts), 2):
        text = parts[index]
        for column in known_columns:
            if not _simple_identifier(column):
                continue
            pattern = rf'(?<![\w"]){re.escape(column)}(?![\w"])'
            text = re.sub(pattern, quote_identifier(column), text)
        parts[index] = text
    return "".join(parts)


def _simple_identifier(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value))


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item) for item in value or ()]  # type: ignore[union-attr]


_PREPARATION_STEPS: tuple[SnowflakePreparationStep, ...] = (
    SnowflakePreparationStep("metadata_projection", _apply_metadata_projection),
    SnowflakePreparationStep("shape_columns", _apply_shape_columns),
    SnowflakePreparationStep("transform_cast", _apply_transform_cast),
    SnowflakePreparationStep("transform_standardize", _apply_transform_standardize),
    SnowflakePreparationStep("transform_derive", _apply_transform_derive),
    SnowflakePreparationStep("filter_expression", _apply_filter_expression),
    SnowflakePreparationStep("transform_composite_keys", _apply_transform_composite_keys),
    SnowflakePreparationStep("transform_deduplicate", _apply_transform_deduplicate),
)

_TRANSFORM_RENDERERS: dict[str, Callable[[str, Any], str]] = {
    "cast": _cast_projection,
    "composite_keys": _composite_key_projection,
    "derive": _derive_projection,
    "standardize": _standardize_projection,
    "deduplicate": _deduplicate_sql,
}


__all__ = ["apply_preparation_sql", "unsupported_preparation_markers"]
