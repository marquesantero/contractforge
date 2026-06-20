"""Render Fabric catalog annotation plans and evidence SQL."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_fabric.evidence import evidence_table_names
from contractforge_fabric.naming import target_table_name
from contractforge_fabric.sql import quote_identifier, quote_table_name, sql_string


def has_annotations(contract: SemanticContract) -> bool:
    annotations = contract.governance.annotations if contract.governance else None
    return bool(isinstance(annotations, dict) and annotation_steps(contract))


def render_annotations_plan(contract: SemanticContract) -> str:
    plan = annotations_plan(contract)
    if not plan["changes"]:
        return ""
    return json.dumps(plan, indent=2, sort_keys=True)


def annotations_plan(contract: SemanticContract) -> dict[str, Any]:
    changes = annotation_steps(contract)
    return {
        "adapter": "fabric",
        "target": target_table_name(contract),
        "status": "PLANNED" if changes else "NOOP",
        "apply_surface": "Fabric Lakehouse catalog metadata",
        "apply_mode": "review_only",
        "note": "Fabric annotation application must be validated against the chosen Lakehouse/catalog metadata API before apply mode is enabled.",
        "changes": changes,
    }


def annotation_steps(contract: SemanticContract) -> list[dict[str, Any]]:
    annotations = contract.governance.annotations if contract.governance else None
    if not isinstance(annotations, dict):
        return []
    table = _mapping(annotations.get("table"))
    rows = _table_changes(table)
    rows.extend(_column_changes(_mapping(annotations.get("columns"))))
    return rows


def render_annotations_evidence_sql(
    contract: SemanticContract,
    *,
    schema: str = "contractforge",
    run_id: str = "${run_id}",
    captured_at_utc: datetime | None = None,
) -> str:
    rows = _annotation_evidence_rows(contract, run_id=run_id, captured_at_utc=captured_at_utc)
    if not rows:
        return "-- No annotation intent declared.\n"
    table = quote_table_name(evidence_table_names(schema)["annotations"])
    return "\n".join(_insert(table, row) for row in rows) + "\n"


def _table_changes(table: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    description = table.get("description")
    if description:
        rows.append(_change("table", "description", None, "description", str(description)))
    for key, value in _table_tags(table).items():
        rows.append(_change("table", "tag", None, key, value))
    return rows


def _column_changes(columns: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for column, config in columns.items():
        data = _mapping(config)
        description = data.get("description")
        if description:
            rows.append(_change("column", "description", str(column), "description", str(description)))
        for key, value in _column_tags(data).items():
            rows.append(_change("column", "tag", str(column), key, value))
    return rows


def _change(scope: str, annotation_type: str, column: str | None, key: str, value: str) -> dict[str, Any]:
    return {
        "annotation_scope": scope,
        "annotation_type": annotation_type,
        "column_name": column,
        "key": key,
        "value": str(redact_value(value)),
        "status": "PLANNED",
    }


def _annotation_evidence_rows(
    contract: SemanticContract,
    *,
    run_id: str,
    captured_at_utc: datetime | None,
) -> list[dict[str, Any]]:
    captured = captured_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    target = target_table_name(contract)
    return [
        {
            "run_id": run_id,
            "target_table": target,
            "annotation_scope": change["annotation_scope"],
            "annotation_type": change["annotation_type"],
            "column_name": change["column_name"],
            "key": change["key"],
            "previous_value": None,
            "value": change["value"],
            "status": change["status"],
            "error_message": None,
            "applied_sql": "fabric_catalog_annotation_plan",
            "annotation_ts_utc": captured,
            "annotation_date": captured.date(),
            "framework_version": "contractforge-fabric",
            "ctrl_schema_version": 1,
        }
        for change in annotation_steps(contract)
    ]


def _table_tags(table: dict[str, Any]) -> dict[str, str]:
    return {
        **_str_map(table.get("tags")),
        **_alias_tags(table.get("aliases")),
        **_deprecated_tags(table.get("deprecated")),
    }


def _column_tags(config: dict[str, Any]) -> dict[str, str]:
    return {
        **_str_map(config.get("tags")),
        **_alias_tags(config.get("aliases")),
        **_pii_tags(config.get("pii")),
        **_deprecated_tags(config.get("deprecated")),
    }


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _str_map(value: object) -> dict[str, str]:
    return {str(key): _tag_value(item) for key, item in redact_value(_mapping(value)).items()}


def _alias_tags(value: object) -> dict[str, str]:
    return {f"alias_{idx}": item for idx, item in enumerate(_as_list(value), start=1)}


def _deprecated_tags(value: object) -> dict[str, str]:
    deprecated = _mapping(value)
    if not deprecated:
        return {}
    tags = {"deprecated": "true"}
    for key in ("since", "replacement", "removal_date"):
        if deprecated.get(key):
            tags[f"deprecated_{key}"] = str(deprecated[key])
    return tags


def _pii_tags(value: object) -> dict[str, str]:
    pii = _mapping(value)
    if not pii:
        return {}
    return {
        "pii": _tag_value(pii.get("enabled", True)),
        "pii_type": str(pii.get("type", "unknown")),
        "sensitivity": str(pii.get("sensitivity", "internal")),
    }


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]  # type: ignore[union-attr]


def _tag_value(value: object) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


def _insert(table: str, columns: dict[str, Any]) -> str:
    names = ", ".join(quote_identifier(name) for name in columns)
    values = ", ".join(_literal(value) for value in columns.values())
    return f"INSERT INTO {table} ({names}) VALUES ({values});"


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP {sql_string(value.strftime('%Y-%m-%d %H:%M:%S'))}"
    if isinstance(value, date):
        return f"DATE {sql_string(value.strftime('%Y-%m-%d'))}"
    return sql_string(redact_value(str(value)))
