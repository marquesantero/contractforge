"""Render AWS Glue transform preparation steps."""

from __future__ import annotations

import re
from typing import Any, Iterable

from contractforge_core.semantic import SemanticContract
from contractforge_aws.preparation.shape import transform_payload
from contractforge_aws.preparation.utils import as_dict, string_list

_ORDER_CLAUSE_RE = re.compile(
    r"^`?(?P<column>[A-Za-z_][A-Za-z0-9_]*)`?(?:\s+(?P<direction>ASC|DESC))?(?:\s+NULLS\s+(?P<nulls>FIRST|LAST))?$",
    re.IGNORECASE,
)


def can_render_transform(contract: SemanticContract) -> bool:
    transform = transform_payload(contract)
    deduplicate = as_dict(transform.get("deduplicate"))
    return not deduplicate or _can_render_deduplicate(deduplicate)


def transform_requires_functions(contract: SemanticContract) -> bool:
    transform = transform_payload(contract)
    return bool(
        transform.get("cast")
        or transform.get("standardize")
        or transform.get("derive")
        or transform.get("composite_keys")
        or transform.get("deduplicate")
    )


def transform_requires_window(contract: SemanticContract) -> bool:
    return bool(transform_payload(contract).get("deduplicate"))


def render_transform_preparation(
    contract: SemanticContract,
    *,
    dataframe_name: str = "df",
    sections: Iterable[str] | None = None,
) -> list[str]:
    transform = transform_payload(contract)
    selected_sections = set(sections) if sections is not None else None
    lines: list[str] = []
    for key, renderer in _TRANSFORM_SECTION_RENDERERS:
        if selected_sections is not None and key not in selected_sections:
            continue
        section = as_dict(transform.get(key))
        if section:
            lines.extend(renderer(section, dataframe_name=dataframe_name))
    return lines


def _cast(casts: dict[str, Any], *, dataframe_name: str) -> list[str]:
    normalized = {str(column): str(data_type) for column, data_type in casts.items()}
    return [
        f"transform_casts = {normalized!r}",
        f"missing_cast_columns = [column for column in transform_casts if column not in {dataframe_name}.columns]",
        "if missing_cast_columns:",
        "    raise ValueError(f'transform.cast references missing columns: {missing_cast_columns}')",
        "for column_name, data_type in transform_casts.items():",
        f"    {dataframe_name} = {dataframe_name}.withColumn(column_name, F.col(column_name).cast(data_type))",
        "",
    ]


def _standardize(standardize: dict[str, Any], *, dataframe_name: str) -> list[str]:
    normalized = {str(column): dict(config or {}) for column, config in standardize.items()}
    return [
        f"transform_standardize = {normalized!r}",
        f"missing_standardize_columns = [column for column in transform_standardize if column not in {dataframe_name}.columns]",
        "if missing_standardize_columns:",
        "    raise ValueError(f'transform.standardize references missing columns: {missing_standardize_columns}')",
        "for column_name, config in transform_standardize.items():",
        "    column_expr = F.col(column_name)",
        "    if config.get('normalize_whitespace'):",
        "        column_expr = F.regexp_replace(column_expr, r'\\s+', ' ')",
        "    if config.get('trim'):",
        "        column_expr = F.trim(column_expr)",
        "    if config.get('lower'):",
        "        column_expr = F.lower(column_expr)",
        "    if config.get('upper'):",
        "        column_expr = F.upper(column_expr)",
        "    if config.get('empty_as_null'):",
        "        column_expr = F.when(column_expr == '', F.lit(None)).otherwise(column_expr)",
        f"    {dataframe_name} = {dataframe_name}.withColumn(column_name, column_expr)",
        "",
    ]


def _derive(expressions: dict[str, Any], *, dataframe_name: str) -> list[str]:
    normalized = {str(column): str(expression) for column, expression in expressions.items()}
    return [
        f"transform_derive = {normalized!r}",
        "for column_name, expression in transform_derive.items():",
        f"    {dataframe_name} = {dataframe_name}.withColumn(column_name, F.expr(expression))",
        "",
    ]


def _composite_keys(composite_keys: dict[str, Any], *, dataframe_name: str) -> list[str]:
    normalized = {str(key): string_list(columns) for key, columns in composite_keys.items()}
    return [
        f"transform_composite_keys = {normalized!r}",
        "for key_name, source_columns in transform_composite_keys.items():",
        f"    missing_composite_columns = [column for column in source_columns if column not in {dataframe_name}.columns]",
        "    if missing_composite_columns:",
        "        raise ValueError(f'transform.composite_keys.{key_name} references missing columns: {missing_composite_columns}')",
        "    composite_parts = [F.coalesce(F.col(column).cast('string'), F.lit('')) for column in source_columns]",
        f"    {dataframe_name} = {dataframe_name}.withColumn(key_name, F.concat_ws('|', *composite_parts))",
        "",
    ]


def _deduplicate(deduplicate: dict[str, Any], *, dataframe_name: str) -> list[str]:
    keys = string_list(deduplicate.get("keys"))
    if not keys:
        raise ValueError("transform.deduplicate.keys is required")
    order_expressions = _order_by_expressions(deduplicate.get("order_by"))
    if not order_expressions:
        raise ValueError("transform.deduplicate.order_by is required")
    order_clause = ", ".join(order_expressions)
    return [
        f"deduplicate_keys = {keys!r}",
        f"missing_deduplicate_keys = [column for column in deduplicate_keys if column not in {dataframe_name}.columns]",
        "if missing_deduplicate_keys:",
        "    raise ValueError(f'transform.deduplicate.keys references missing columns: {missing_deduplicate_keys}')",
        f"deduplicate_window = Window.partitionBy(*deduplicate_keys).orderBy({order_clause})",
        f"{dataframe_name} = (",
        f"    {dataframe_name}.withColumn('__cf_row_number', F.row_number().over(deduplicate_window))",
        "    .filter(F.col('__cf_row_number') == 1)",
        "    .drop('__cf_row_number')",
        ")",
        "",
    ]


def _order_by_expressions(order_by: object) -> list[str]:
    if isinstance(order_by, str):
        return _order_by_from_string(order_by)
    expressions: list[str] = []
    for item in order_by or ():
        if not isinstance(item, dict) or not item.get("column"):
            continue
        expressions.append(
            _order_column_expression(
                str(item["column"]),
                direction=str(item.get("direction", "desc")).lower(),
                nulls=str(item.get("nulls") or "").lower(),
            )
        )
    return expressions


def _order_by_from_string(order_by: str) -> list[str]:
    expressions: list[str] = []
    for clause in (item.strip() for item in order_by.split(",")):
        if not clause:
            continue
        parsed = _ORDER_CLAUSE_RE.match(clause)
        if parsed is None:
            raise ValueError(
                "AWS transform.deduplicate.order_by string clauses must be simple column references. "
                "Use list entries with {column, direction, nulls} for portable ordering."
            )
        expressions.append(
            _order_column_expression(
                parsed.group("column"),
                direction=(parsed.group("direction") or "desc").lower(),
                nulls=(parsed.group("nulls") or "").lower(),
            )
        )
    return expressions


def _can_render_deduplicate(deduplicate: dict[str, Any]) -> bool:
    order_by = deduplicate.get("order_by")
    if isinstance(order_by, str):
        return all(_ORDER_CLAUSE_RE.match(clause.strip()) for clause in order_by.split(",") if clause.strip())
    return True


def _order_column_expression(column: str, *, direction: str, nulls: str) -> str:
    direction = "asc" if direction == "asc" else "desc"
    suffix = f"_nulls_{nulls}" if nulls in {"first", "last"} else ""
    return f"F.col({column!r}).{direction}{suffix}()"


_TRANSFORM_SECTION_RENDERERS = (
    ("cast", _cast),
    ("standardize", _standardize),
    ("derive", _derive),
    ("composite_keys", _composite_keys),
    ("deduplicate", _deduplicate),
)
