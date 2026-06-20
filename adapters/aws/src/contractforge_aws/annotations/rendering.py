"""Render AWS Glue Catalog annotation plans and evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from functools import singledispatch
from typing import Any, Callable

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names
from contractforge_aws.rendering.names import glue_database_name, glue_table_name, iceberg_table_name


@dataclass(frozen=True)
class _TagExtractor:
    prefix: str
    extract: Callable[[dict[str, Any]], dict[str, str]]


_TABLE_TAG_EXTRACTORS: tuple[_TagExtractor, ...] = (
    _TagExtractor("", lambda data: _str_map(data.get("tags"))),
    _TagExtractor("alias_", lambda data: _indexed_tags(data.get("aliases"))),
    _TagExtractor("deprecated_", lambda data: _deprecated_tags(data.get("deprecated"))),
)
_COLUMN_TAG_EXTRACTORS: tuple[_TagExtractor, ...] = (
    *_TABLE_TAG_EXTRACTORS,
    _TagExtractor("pii_", lambda data: _pii_tags(data.get("pii"))),
)


def render_annotations_plan(contract: SemanticContract) -> str:
    plan = annotations_plan(contract)
    if not plan["changes"]:
        return ""
    return json.dumps(plan, indent=2, sort_keys=True)


def annotations_plan(contract: SemanticContract) -> dict[str, Any]:
    annotations = contract.governance.annotations if contract.governance else None
    changes = _annotation_changes(annotations if isinstance(annotations, dict) else {})
    return {
        "target": iceberg_table_name(contract),
        "resource": {"DatabaseName": glue_database_name(contract), "Name": glue_table_name(contract)},
        "status": "PLANNED" if changes else "NOOP",
        "apply_operation": "glue:UpdateTable",
        "note": "Application requires reading the current Glue table definition and submitting a full TableInput.",
        "changes": changes,
    }


def render_annotations_evidence_sql(contract: SemanticContract, *, database: str, run_id: str = "${run_id}", captured_at_utc: datetime | None = None) -> str:
    rows = _annotation_evidence_rows(contract, run_id=run_id, captured_at_utc=captured_at_utc)
    if not rows:
        return "-- No annotation intent declared.\n"
    table = evidence_table_names(database)["annotations"]
    return "\n".join(_insert(table, row) for row in rows) + "\n"


def _annotation_changes(annotations: dict[str, Any]) -> list[dict[str, Any]]:
    table = _mapping(annotations.get("table"))
    rows = _table_changes(table)
    rows.extend(_column_changes(_mapping(annotations.get("columns"))))
    return rows


def _table_changes(table: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    description = table.get("description")
    if description:
        rows.append(_change("table", "description", None, "Description", str(description)))
    for key, value in _tags(table, _TABLE_TAG_EXTRACTORS).items():
        rows.append(_change("table", "parameter", None, f"Parameters.{key}", value, key=key))
    return rows


def _column_changes(columns: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for column, config in columns.items():
        data = _mapping(config)
        description = data.get("description")
        if description:
            rows.append(
                _change("column", "description", str(column), "StorageDescriptor.Columns[].Comment", str(description))
            )
        for key, value in _tags(data, _COLUMN_TAG_EXTRACTORS).items():
            rows.append(_change("column", "parameter", str(column), "StorageDescriptor.Columns[].Parameters." + key, value, key=key))
    return rows


def _change(scope: str, kind: str, column: str | None, glue_path: str, value: str, *, key: str | None = None) -> dict[str, Any]:
    return {
        "annotation_scope": scope,
        "annotation_type": kind,
        "column_name": column,
        "key": key or kind,
        "value": value,
        "glue_path": glue_path,
        "status": "PLANNED",
    }


def _annotation_evidence_rows(contract: SemanticContract, *, run_id: str, captured_at_utc: datetime | None) -> list[dict[str, Any]]:
    captured = captured_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    target = iceberg_table_name(contract)
    return [
        {
            "run_id": run_id,
            "target_table": target,
            "annotation_scope": change["annotation_scope"],
            "annotation_type": change["annotation_type"],
            "column_name": change["column_name"],
            "key": change["key"],
            "value": change["value"],
            "status": change["status"],
            "applied_sql": "glue:UpdateTable",
            "annotation_ts_utc": captured,
            "annotation_date": captured.date(),
            "framework_version": "contractforge-aws",
            "ctrl_schema_version": 1,
        }
        for change in annotations_plan(contract)["changes"]
    ]


def _tags(data: dict[str, Any], extractors: tuple[_TagExtractor, ...]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for extractor in extractors:
        tags.update({f"{extractor.prefix}{key}": value for key, value in extractor.extract(data).items()})
    return tags


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _str_map(value: object) -> dict[str, str]:
    return {str(key): _tag_value(item) for key, item in _mapping(value).items()}


def _indexed_tags(value: object) -> dict[str, str]:
    return {str(idx): item for idx, item in enumerate(_as_list(value), start=1)}


def _deprecated_tags(value: object) -> dict[str, str]:
    deprecated = _mapping(value)
    if not deprecated:
        return {}
    return {"enabled": "true", **{key: str(deprecated[key]) for key in ("since", "replacement", "removal_date") if deprecated.get(key)}}


def _pii_tags(value: object) -> dict[str, str]:
    pii = _mapping(value)
    if not pii:
        return {}
    return {
        "enabled": _tag_value(pii.get("enabled", True)),
        "type": str(pii.get("type", "unknown")),
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
    filtered = {key: value for key, value in columns.items() if value is not None}
    names = ", ".join(_quote_identifier(name) for name in filtered)
    values = ", ".join(_literal(value) for value in filtered.values())
    return f"INSERT INTO {table} ({names}) VALUES ({values});"


@singledispatch
def _literal(value: Any) -> str:
    return _string(str(redact_value(value)))


@_literal.register(int)
def _literal_int(value: int) -> str:
    return str(value)


@_literal.register(datetime)
def _literal_datetime(value: datetime) -> str:
    return f"TIMESTAMP {_string(value.strftime('%Y-%m-%d %H:%M:%S'))}"


@_literal.register(date)
def _literal_date(value: date) -> str:
    return f"DATE {_string(value.strftime('%Y-%m-%d'))}"


def _string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_identifier(value: str) -> str:
    return f"`{str(value).replace('`', '``')}`"
