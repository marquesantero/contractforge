"""Render Fabric notebook shape.flatten preparation steps."""

from __future__ import annotations

from typing import Any


def flatten_config(value: object) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"enabled": value, "separator": "_", "max_depth": 10, "include": [], "exclude": []}
    config = _as_dict(value)
    if not config:
        return {"enabled": False}
    return {
        "enabled": bool(config.get("enabled", False)),
        "separator": str(config.get("separator", "_")),
        "max_depth": int(config.get("max_depth", 10)),
        "include": _string_list(config.get("include")),
        "exclude": _string_list(config.get("exclude")),
    }


def render_flatten(config: dict[str, Any], *, dataframe_name: str) -> list[str]:
    return [
        f"{dataframe_name} = _cf_flatten(",
        f"    {dataframe_name},",
        f"    separator={config['separator']!r},",
        f"    max_depth={int(config['max_depth'])},",
        f"    include={config['include']!r},",
        f"    exclude={config['exclude']!r},",
        ")",
        "",
    ]


def render_flatten_helper() -> str:
    return "\n".join(
        [
            "def _cf_flatten(df, separator, max_depth, include, exclude):",
            '    """Flatten nested struct columns to leaf paths at Fabric notebook runtime."""',
            "    from pyspark.sql import functions as F",
            "    from pyspark.sql.types import StructType",
            "",
            "    include = set(include or [])",
            "    exclude = set(exclude or [])",
            "",
            "    def _excluded(path):",
            "        return path in exclude or any(path.startswith(item + '.') for item in exclude)",
            "",
            "    def _leaves(struct, prefix, depth):",
            "        result = []",
            "        for field in struct.fields:",
            "            path = prefix + '.' + field.name",
            "            if isinstance(field.dataType, StructType) and depth < max_depth:",
            "                result.extend(_leaves(field.dataType, path, depth + 1))",
            "            else:",
            "                result.append((path, path.replace('.', separator)))",
            "        return result",
            "",
            "    top_level = set(df.columns)",
            "    projections = []",
            "    aliases = set()",
            "    for field in df.schema.fields:",
            "        if (include and field.name not in include) or _excluded(field.name):",
            "            projections.append(F.col(field.name).alias(field.name))",
            "            aliases.add(field.name)",
            "            continue",
            "        if isinstance(field.dataType, StructType):",
            "            for path, alias in _leaves(field.dataType, field.name, 1):",
            "                if _excluded(path) or alias in top_level:",
            "                    continue",
            "                if alias in aliases:",
            "                    raise ValueError('shape.flatten would create duplicate column: ' + alias)",
            "                projections.append(F.col(path).alias(alias))",
            "                aliases.add(alias)",
            "        else:",
            "            projections.append(F.col(field.name).alias(field.name))",
            "            aliases.add(field.name)",
            "    return df.select(*projections) if projections else df",
            "",
        ]
    )


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]  # type: ignore[union-attr]


__all__ = ["flatten_config", "render_flatten", "render_flatten_helper"]
