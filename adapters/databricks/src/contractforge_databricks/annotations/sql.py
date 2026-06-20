"""Render Unity Catalog annotations SQL."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.coercion import mapping, string_list, string_map
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_identifier, quote_table_name, sql_string


def annotation_steps(contract: SemanticContract) -> list[dict[str, Any]]:
    annotations = contract.governance.annotations if contract.governance else None
    if not isinstance(annotations, dict):
        return []

    target = target_full_name(contract)
    quoted_target = quote_table_name(target)
    steps: list[dict[str, Any]] = []
    table = mapping(annotations.get("table"))
    if table.get("description"):
        steps.append(
            {
                "annotation_scope": "table",
                "annotation_type": "description",
                "column_name": None,
                "key": "description",
                "value": str(table["description"]),
                "sql": f"COMMENT ON TABLE {quoted_target} IS {sql_string(table['description'])}",
            }
        )
    _append_tag_step(steps, quoted_target, None, _table_tags(table))
    for column, config in mapping(annotations.get("columns")).items():
        _append_column_steps(steps, quoted_target, str(column), mapping(config))
    return steps


def render_annotations_sql(contract: SemanticContract) -> str:
    annotations = contract.governance.annotations if contract.governance else None
    if not isinstance(annotations, dict):
        return "-- No annotations intent declared.\n"

    target = target_full_name(contract)
    lines = [
        "-- Review before execution. Unity Catalog tags require UC-enabled targets.",
        f"-- Target: {target}",
        "",
    ]
    lines.extend(f"{step['sql']};" for step in annotation_steps(contract))
    return "\n".join(lines) + "\n"


def _append_column_steps(
    steps: list[dict[str, Any]],
    quoted_target: str,
    column: str,
    config: dict[str, Any],
) -> None:
    quoted_column = quote_identifier(column)
    if config.get("description"):
        steps.append(
            {
                "annotation_scope": "column",
                "annotation_type": "description",
                "column_name": column,
                "key": "description",
                "value": str(config["description"]),
                "sql": f"ALTER TABLE {quoted_target} ALTER COLUMN {quoted_column} COMMENT {sql_string(config['description'])}",
            }
        )
    _append_tag_step(steps, quoted_target, column, _column_tags(config))


def _append_tag_step(steps: list[dict[str, Any]], quoted_target: str, column: str | None, tags: dict[str, str]) -> None:
    if tags:
        sql = f"ALTER TABLE {quoted_target} SET TAGS ({_tag_sql(tags)})"
        if column is not None:
            sql = f"ALTER TABLE {quoted_target} ALTER COLUMN {quote_identifier(column)} SET TAGS ({_tag_sql(tags)})"
        steps.append(
            {
                "annotation_scope": "column" if column else "table",
                "annotation_type": "tags",
                "column_name": column,
                "key": "tags",
                "value": _json(tags),
                "sql": sql,
            }
        )


def _table_tags(table: dict[str, Any]) -> dict[str, str]:
    return {
        **string_map(table.get("tags")),
        **_alias_tags(table.get("aliases")),
        **_deprecated_tags(table.get("deprecated")),
    }


def _column_tags(config: dict[str, Any]) -> dict[str, str]:
    return {
        **string_map(config.get("tags")),
        **_alias_tags(config.get("aliases")),
        **_pii_tags(config.get("pii")),
        **_deprecated_tags(config.get("deprecated")),
    }


def _alias_tags(value: object) -> dict[str, str]:
    return {f"alias_{idx}": alias for idx, alias in enumerate(string_list(value, sep="|"), start=1)}


def _deprecated_tags(value: object) -> dict[str, str]:
    deprecated = mapping(value)
    if not deprecated:
        return {}
    tags = {"deprecated": "true"}
    for key in ("since", "replacement", "removal_date"):
        if deprecated.get(key):
            tags[f"deprecated_{key}"] = str(deprecated[key])
    return tags


def _pii_tags(value: object) -> dict[str, str]:
    pii = mapping(value)
    if not pii:
        return {}
    return {
        "pii": str(pii.get("enabled", True)).lower(),
        "pii_type": str(pii.get("type", "unknown")),
        "sensitivity": str(pii.get("sensitivity", "internal")),
    }


def _tag_sql(tags: dict[str, str]) -> str:
    return ", ".join(f"{sql_string(key)} = {sql_string(value)}" for key, value in tags.items())


def _json(value: dict[str, str]) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))
