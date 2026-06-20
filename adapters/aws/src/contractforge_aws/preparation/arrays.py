"""Render AWS Glue shape.arrays steps with cardinality guardrails."""

from __future__ import annotations

from typing import Any

from contractforge_aws.preparation.utils import as_dict

CARDINALITY_CHANGING_MODES = frozenset({"explode", "explode_outer"})
# Standard Spark column expressions, all supported by AWS Glue.
_ARRAY_MODE_EXPRESSIONS = {
    "to_json": "F.to_json({col})",
    "size": "F.size({col})",
    "first": "F.element_at({col}, 1)",
    "explode": "F.explode({col})",
    "explode_outer": "F.explode_outer({col})",
}


def render_arrays(configs: list[Any], *, dataframe_name: str) -> list[str]:
    lines: list[str] = []
    for config in configs:
        config = as_dict(config)
        mode = str(config.get("mode") or "keep")
        if mode == "keep":
            continue
        path = str(config["path"])
        alias = str(config.get("alias") or path.replace(".", "_"))
        expression = _ARRAY_MODE_EXPRESSIONS[mode].format(col=f"F.col({path!r})")
        lines.append(f"{dataframe_name} = {dataframe_name}.withColumn({alias!r}, {expression})")
    if lines:
        lines.append("")
    return lines


def arrays_require_functions(arrays: list[Any]) -> bool:
    return any(as_dict(config).get("mode", "keep") != "keep" for config in arrays or [])


def can_render_arrays(shape: dict[str, Any], *, layer: str) -> bool:
    arrays = [as_dict(config) for config in shape.get("arrays") or []]
    if not arrays:
        return True
    if any(not config.get("path") for config in arrays):
        return False
    if not _cardinality_allowed(shape, arrays, layer=layer):
        return False
    return not _has_cartesian_conflict(arrays)


def _cardinality_allowed(shape: dict[str, Any], arrays: list[dict[str, Any]], *, layer: str) -> bool:
    if layer != "bronze" or shape.get("allow_cardinality_change_on_bronze"):
        return True
    return not any(config.get("mode") in CARDINALITY_CHANGING_MODES for config in arrays)


def _has_cartesian_conflict(arrays: list[dict[str, Any]]) -> bool:
    groups: dict[str, list[dict[str, Any]]] = {}
    for config in arrays:
        if config.get("mode") not in CARDINALITY_CHANGING_MODES:
            continue
        parent = str(config["path"]).rsplit(".", 1)[0] if "." in str(config["path"]) else ""
        groups.setdefault(parent, []).append(config)
    return any(
        len(siblings) > 1 and any(not config.get("allow_cartesian") for config in siblings)
        for siblings in groups.values()
    )
