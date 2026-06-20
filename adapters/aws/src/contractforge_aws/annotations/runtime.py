"""Optional AWS Glue Catalog annotation apply helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from contractforge_aws.runtime.dependencies import require_boto3


@dataclass(frozen=True)
class GlueCatalogAnnotationApplyResult:
    database: str
    table: str
    status: str
    applied: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class AnnotationChangeHandler:
    scope: str
    kind: str
    apply: Callable[[dict[str, Any], dict[str, Any]], None]

    @property
    def key(self) -> tuple[str, str]:
        return self.scope, self.kind


def apply_glue_catalog_annotations_plan(
    plan: str | dict[str, Any],
    *,
    glue_client: Any | None = None,
    catalog_id: str | None = None,
    skip_archive: bool = True,
) -> GlueCatalogAnnotationApplyResult:
    payload = _plan_payload(plan)
    resource = _resource(payload)
    changes = _changes(payload)
    if not changes:
        return GlueCatalogAnnotationApplyResult(resource["DatabaseName"], resource["Name"], "NOOP")

    client = glue_client or require_boto3().client("glue")
    get_args = _catalog_args(catalog_id, DatabaseName=resource["DatabaseName"], Name=resource["Name"])
    table = client.get_table(**get_args)["Table"]
    table_input = _table_input(table)
    applied = _apply_changes(table_input, changes)
    update_args = _catalog_args(
        catalog_id,
        DatabaseName=resource["DatabaseName"],
        Name=resource["Name"],
        TableInput=table_input,
        SkipArchive=skip_archive,
    )
    client.update_table(**update_args)
    return GlueCatalogAnnotationApplyResult(resource["DatabaseName"], resource["Name"], "SUCCESS", applied=applied)


def _plan_payload(plan: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(plan, str):
        loaded = json.loads(plan)
        if not isinstance(loaded, dict):
            raise ValueError("Glue Catalog annotation plan JSON must decode to an object")
        return loaded
    return dict(plan)


def _resource(plan: dict[str, Any]) -> dict[str, str]:
    resource = plan.get("resource")
    if not isinstance(resource, dict):
        raise ValueError("Glue Catalog annotation plan requires resource")
    database = str(resource.get("DatabaseName") or "").strip()
    table = str(resource.get("Name") or "").strip()
    if not database or not table:
        raise ValueError("Glue Catalog annotation plan requires resource.DatabaseName and resource.Name")
    return {"DatabaseName": database, "Name": table}


def _changes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    changes = plan.get("changes")
    if not isinstance(changes, list):
        return []
    return [dict(item) for item in changes if isinstance(item, dict)]


def _table_input(table: dict[str, Any]) -> dict[str, Any]:
    return {key: table[key] for key in _TABLE_INPUT_KEYS if key in table and table[key] is not None}


def _apply_changes(table_input: dict[str, Any], changes: list[dict[str, Any]]) -> int:
    applied = 0
    for change in changes:
        handler = _CHANGE_HANDLERS.get((str(change.get("annotation_scope")), str(change.get("annotation_type"))))
        if handler is not None:
            handler.apply(table_input, change)
            applied += 1
    return applied


def _apply_table_description(table_input: dict[str, Any], change: dict[str, Any]) -> None:
    table_input["Description"] = str(change.get("value") or "")


def _apply_table_parameter(table_input: dict[str, Any], change: dict[str, Any]) -> None:
    _parameters(table_input)[str(change["key"])] = str(change.get("value") or "")


def _apply_column_description(table_input: dict[str, Any], change: dict[str, Any]) -> None:
    _column(table_input, str(change["column_name"]))["Comment"] = str(change.get("value") or "")


def _apply_column_parameter(table_input: dict[str, Any], change: dict[str, Any]) -> None:
    column = _column(table_input, str(change["column_name"]))
    column.setdefault("Parameters", {})[str(change["key"])] = str(change.get("value") or "")


def _parameters(table_input: dict[str, Any]) -> dict[str, str]:
    value = table_input.setdefault("Parameters", {})
    if not isinstance(value, dict):
        raise ValueError("Glue table Parameters must be an object")
    return value


def _column(table_input: dict[str, Any], name: str) -> dict[str, Any]:
    columns = table_input.get("StorageDescriptor", {}).get("Columns")
    if not isinstance(columns, list):
        raise ValueError("Glue table StorageDescriptor.Columns is required for column annotations")
    for column in columns:
        if isinstance(column, dict) and column.get("Name") == name:
            return column
    raise ValueError(f"Glue table does not contain column {name!r}")


def _catalog_args(catalog_id: str | None, **kwargs: Any) -> dict[str, Any]:
    payload = dict(kwargs)
    if catalog_id:
        payload["CatalogId"] = catalog_id
    return payload


_TABLE_INPUT_KEYS = (
    "Name",
    "Description",
    "Owner",
    "LastAccessTime",
    "LastAnalyzedTime",
    "Retention",
    "StorageDescriptor",
    "PartitionKeys",
    "ViewOriginalText",
    "ViewExpandedText",
    "TableType",
    "Parameters",
    "TargetTable",
)


_CHANGE_HANDLERS = {
    handler.key: handler
    for handler in (
        AnnotationChangeHandler("table", "description", _apply_table_description),
        AnnotationChangeHandler("table", "parameter", _apply_table_parameter),
        AnnotationChangeHandler("column", "description", _apply_column_description),
        AnnotationChangeHandler("column", "parameter", _apply_column_parameter),
    )
}
