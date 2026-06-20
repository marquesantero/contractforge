"""Validation helpers for Databricks shape execution."""

from __future__ import annotations

from typing import Any

CARDINALITY_CHANGING_MODES = frozenset({"explode", "explode_outer"})


def validate_cardinality_policy(shape: dict[str, Any], layer: str) -> None:
    if layer != "bronze" or shape.get("allow_cardinality_change_on_bronze"):
        return
    changing = [item["path"] for item in as_list(shape.get("arrays")) if item.get("mode") in CARDINALITY_CHANGING_MODES]
    if changing:
        raise ValueError(f"shape cardinality change is blocked in bronze by default: {changing}")


def validate_cartesian_arrays(shape: dict[str, Any]) -> None:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in as_list(shape.get("arrays")):
        if item.get("mode") not in CARDINALITY_CHANGING_MODES:
            continue
        groups.setdefault(parent_path(str(item["path"])), []).append(item)
    conflicts = {
        parent: [str(item["path"]) for item in items if not item.get("allow_cartesian")]
        for parent, items in groups.items()
        if len(items) > 1 and any(not item.get("allow_cartesian") for item in items)
    }
    if conflicts:
        raise ValueError(f"shape contains sibling explodes that may create a cartesian product: {conflicts}")


def validate_columns(df: Any, columns: dict[str, Any], context: str) -> None:
    available = set(getattr(df, "columns", ()) or ())
    missing = sorted(str(column) for column in columns if str(column).split(".", 1)[0] not in available)
    if missing:
        raise ValueError(f"{context} references missing columns: {missing}")


def data_type_at_path(schema: Any, path: str) -> Any | None:
    from pyspark.sql.types import ArrayType, StructType

    current = schema
    for part in path.split("."):
        if isinstance(current, ArrayType):
            current = current.elementType
        if not isinstance(current, StructType):
            return None
        field = next((item for item in current.fields if item.name == part), None)
        if field is None:
            return None
        current = field.dataType
    return current


def flatten_config(flatten: object) -> dict[str, Any]:
    if isinstance(flatten, bool):
        return {"enabled": flatten, "separator": "_", "max_depth": 10, "include": [], "exclude": []}
    config = as_dict(flatten)
    return {
        "enabled": bool(config.get("enabled", False)),
        "separator": config.get("separator", "_"),
        "max_depth": config.get("max_depth", 10),
        "include": string_list(config.get("include")),
        "exclude": string_list(config.get("exclude")),
    }


def path_col(functions: Any, path: str) -> Any:
    return functions.col(".".join(f"`{part}`" for part in path.split(".")))


def parent_path(path: str) -> str:
    return ".".join(path.split(".")[:-1])


def is_excluded(path: str, exclude: set[str]) -> bool:
    return path in exclude or any(path.startswith(f"{item}.") for item in exclude)


def as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def as_list(value: object) -> list[dict[str, Any]]:
    return [dict(item) for item in value or () if isinstance(item, dict)]


def string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]  # type: ignore[union-attr]
