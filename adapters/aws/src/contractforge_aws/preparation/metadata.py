"""Render AWS Glue preparation from portable operation metadata."""

from __future__ import annotations

from typing import Any

from contractforge_core.config import CONTROL_COLUMNS
from contractforge_aws.preparation.utils import as_dict, string_list


def render_metadata_preparation(
    metadata: dict[str, Any],
    *,
    dataframe_name: str = "df",
    include_projection: bool = True,
    include_filter: bool = True,
) -> list[str]:
    lines: list[str] = []
    if include_projection:
        select_columns = string_list(metadata.get("select_columns"))
        if select_columns:
            lines.extend(_select_columns(select_columns, dataframe_name=dataframe_name))
        column_mapping = as_dict(metadata.get("column_mapping"))
        if column_mapping:
            lines.extend(_column_mapping(column_mapping, dataframe_name=dataframe_name))
    if include_filter:
        filter_expression = metadata.get("filter_expression")
        if filter_expression:
            lines.extend(_filter_expression(str(filter_expression), dataframe_name=dataframe_name))
    return lines


def _select_columns(columns: list[str], *, dataframe_name: str) -> list[str]:
    return [
        f"select_columns = {columns!r}",
        f"missing_select_columns = [column for column in select_columns if column not in {dataframe_name}.columns]",
        "if missing_select_columns:",
        "    raise ValueError(f'select_columns references missing columns: {missing_select_columns}')",
        f"{dataframe_name} = {dataframe_name}.select(*select_columns)",
        "",
    ]


def _column_mapping(mapping: dict[str, Any], *, dataframe_name: str) -> list[str]:
    normalized = {str(source): str(target) for source, target in mapping.items()}
    reserved_targets = sorted(set(normalized.values()) & CONTROL_COLUMNS)
    if reserved_targets:
        raise ValueError(f"column_mapping cannot produce reserved control columns: {reserved_targets}")
    return [
        f"column_mapping = {normalized!r}",
        f"missing_mapping_columns = [source for source in column_mapping if source not in {dataframe_name}.columns]",
        "if missing_mapping_columns:",
        "    raise ValueError(f'column_mapping references missing columns: {missing_mapping_columns}')",
        "mapping_targets = list(column_mapping.values())",
        "duplicate_mapping_targets = sorted({target for target in mapping_targets if mapping_targets.count(target) > 1})",
        "if duplicate_mapping_targets:",
        "    raise ValueError(f'column_mapping has duplicate targets: {duplicate_mapping_targets}')",
        f"existing_columns = set({dataframe_name}.columns)",
        "mapping_collisions = sorted(",
        "    target",
        "    for source, target in column_mapping.items()",
        "    if target in existing_columns and target != source",
        ")",
        "if mapping_collisions:",
        "    raise ValueError(f'column_mapping would collide with existing columns: {mapping_collisions}')",
        "for source_column, target_column in column_mapping.items():",
        f"    {dataframe_name} = {dataframe_name}.withColumnRenamed(source_column, target_column)",
        "",
    ]


def _filter_expression(expression: str, *, dataframe_name: str) -> list[str]:
    return [
        f"filter_expression = {expression!r}",
        f"{dataframe_name} = {dataframe_name}.where(filter_expression)",
        "",
    ]
