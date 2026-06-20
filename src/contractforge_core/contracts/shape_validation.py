"""Portable semantic validation for shape contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contractforge_core.config import ARRAY_MODES

CARDINALITY_CHANGING_ARRAY_MODES = {"explode", "explode_outer"}


def validate_shape_semantics(shape: Mapping[str, Any] | None, *, context: str = "shape") -> None:
    """Validate shape rules that do not depend on a platform runtime."""

    if not isinstance(shape, Mapping):
        return
    _validate_parse_json(shape.get("parse_json"), context)
    _validate_flatten(shape.get("flatten"), context)
    _validate_zip_arrays(shape.get("zip_arrays"), context)
    _validate_arrays(shape.get("arrays"), context)
    _validate_columns(shape.get("columns"), context)


def _validate_parse_json(value: object, context: str) -> None:
    outputs: set[str] = set()
    for idx, item in enumerate(_mapping_list(value)):
        field = f"{context}.parse_json.{idx}"
        column = _required_text(item.get("column"), f"{field}.column")
        schema = _optional_text(item.get("schema"))
        schema_ref = _optional_text(item.get("schema_ref"))
        if schema and schema_ref:
            raise ValueError(f"{field} must declare schema or schema_ref, not both")
        if not schema and not schema_ref:
            raise ValueError(f"{field} requires schema or schema_ref")
        alias = _optional_text(item.get("alias"))
        output = alias or column
        if "." in output:
            raise ValueError(f"{field}.alias is required when column is a nested path: {column}")
        if item.get("drop_source") and "." in column:
            raise ValueError(f"{field}.drop_source is not supported for nested paths: {column}")
        if output in outputs:
            raise ValueError(f"{context}.parse_json has duplicate output column: {output}")
        outputs.add(output)


def _validate_flatten(value: object, context: str) -> None:
    if value is None or isinstance(value, bool):
        return
    if not isinstance(value, Mapping):
        return
    separator = _optional_text(value.get("separator"))
    if separator == "":
        raise ValueError(f"{context}.flatten.separator cannot be empty")


def _validate_zip_arrays(value: object, context: str) -> None:
    aliases: set[str] = set()
    for idx, item in enumerate(_mapping_list(value)):
        field = f"{context}.zip_arrays.{idx}"
        alias = _required_text(item.get("alias"), f"{field}.alias")
        columns = item.get("columns")
        if not isinstance(columns, Mapping):
            raise ValueError(f"{field}.columns must be an object/dict")
        if len(columns) < 2:
            raise ValueError(f"{field}.columns must declare at least two arrays")
        outputs: set[str] = set()
        for path, output_alias in columns.items():
            _required_text(path, f"{field}.columns.<path>")
            output = _required_text(output_alias, f"{field}.columns.{path}")
            if output in outputs:
                raise ValueError(f"{field} has duplicate output field: {output}")
            outputs.add(output)
        if alias in aliases:
            raise ValueError(f"{context}.zip_arrays has duplicate alias: {alias}")
        aliases.add(alias)


def _validate_arrays(value: object, context: str) -> None:
    for idx, item in enumerate(_mapping_list(value)):
        field = f"{context}.arrays.{idx}"
        _required_text(item.get("path"), f"{field}.path")
        mode = _optional_text(item.get("mode")) or "keep"
        if mode not in ARRAY_MODES:
            raise ValueError(f"{field}.mode must be one of {sorted(ARRAY_MODES)}")


def _validate_columns(value: object, context: str) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        raise ValueError(f"{context}.columns must be an object/dict")
    aliases: set[str] = set()
    for path, config in value.items():
        source_path = _required_text(path, f"{context}.columns.<path>")
        alias = _column_alias(source_path, config, context)
        if alias in aliases:
            raise ValueError(f"{context}.columns has duplicate alias: {alias}")
        aliases.add(alias)


def _column_alias(source_path: str, config: object, context: str) -> str:
    if isinstance(config, str):
        return _required_text(config, f"{context}.columns.{source_path}.alias")
    if isinstance(config, Mapping):
        alias = _optional_text(config.get("alias"))
        return alias or source_path.replace(".", "_")
    raise ValueError(f"{context}.columns.{source_path} must be a string or object")


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    return [item for item in value if isinstance(item, Mapping)]  # type: ignore[union-attr]


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} cannot be empty")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value).strip()
