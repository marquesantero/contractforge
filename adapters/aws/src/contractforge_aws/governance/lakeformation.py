"""Render AWS Lake Formation review/apply artifacts from the access contract.

Lake Formation governs *read* access on the consumer side. Three mappings:

* ``access.grants`` -> ``lakeformation:GrantPermissions`` requests. These are
  directly applyable.
* ``access.row_filters`` -> ``CreateDataCellsFilter`` scaffolds. Lake Formation
  data filters use a SQL ``FilterExpression``, not the row-filter *function*
  the contract references, so the expression cannot be derived automatically.
  The scaffold is rendered fail-closed (``false`` = deny all rows) with a TODO
  until a reviewer translates the function into a predicate.
* ``access.column_masks`` -> ``CreateDataCellsFilter`` scaffolds that exclude
  the masked column (column-level security). Lake Formation has no value-level
  masking function, so a transformed value must be produced in the ingestion
  job or a consumer view instead.

This artifact does not change planning status: row filters and column masks
stay ``REVIEW_REQUIRED``. It makes the Lake Formation design concrete.
"""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_aws.rendering.names import glue_database_name, glue_table_name

_ACCOUNT_PLACEHOLDER = "REPLACE_WITH_AWS_ACCOUNT_ID"


def can_render_lake_formation(contract: SemanticContract) -> bool:
    access = _access(contract)
    return bool(access.get("grants") or access.get("row_filters") or access.get("column_masks"))


def render_lake_formation_plan(contract: SemanticContract) -> dict[str, Any]:
    """Build the structured Lake Formation plan (permissions + data filters)."""

    access = _access(contract)
    database = glue_database_name(contract)
    table = glue_table_name(contract)
    plan: dict[str, Any] = {
        "resource": {"DatabaseName": database, "TableName": table},
        "permissions": _grants(access.get("grants", ()), database=database, table=table),
        "data_cells_filters": [
            *_row_filters(access.get("row_filters", ()), database=database, table=table),
            *_column_masks(access.get("column_masks", ()), database=database, table=table),
        ],
        "notes": [
            "Lake Formation governs read access on the consumer side; it is not write-time row rejection.",
            "Set TableCatalogId to the data lake AWS account id before applying data cell filters.",
        ],
    }
    return redact_value(plan)


def render_lake_formation_artifact(contract: SemanticContract) -> str:
    """Render the Lake Formation plan as JSON, or '' when nothing maps."""

    if not can_render_lake_formation(contract):
        return ""
    return json.dumps(render_lake_formation_plan(contract), indent=2, sort_keys=True) + "\n"


def _grants(grants: Any, *, database: str, table: str) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for grant in grants or ():
        if not isinstance(grant, dict):
            continue
        principal = str(grant.get("principal") or "").strip()
        if not principal:
            continue
        requests.append(
            {
                "Principal": {"DataLakePrincipalIdentifier": principal},
                "Resource": {"Table": {"DatabaseName": database, "Name": table}},
                "Permissions": _permissions(grant.get("privileges")),
                "PermissionsWithGrantOption": [],
            }
        )
    return requests


def _row_filters(row_filters: Any, *, database: str, table: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for row_filter in row_filters or ():
        if not isinstance(row_filter, dict):
            continue
        name = _safe_filter_name(str(row_filter.get("name") or row_filter.get("function") or "row_filter"))
        function = str(row_filter.get("function") or "")
        columns = _as_list(row_filter.get("columns"))
        principals = _principals(row_filter.get("applies_to"))
        entries.append(
            {
                "create_data_cells_filter": {
                    "TableData": {
                        "TableCatalogId": _ACCOUNT_PLACEHOLDER,
                        "DatabaseName": database,
                        "TableName": table,
                        "Name": name,
                        "RowFilter": {"FilterExpression": "false"},
                        "ColumnWildcard": {},
                    }
                },
                "grants": _data_filter_grants(principals, database=database, table=table, name=name),
                "todo": (
                    f"Translate row-filter function {function!r} over columns {columns} into a Lake Formation "
                    "FilterExpression. The scaffold denies all rows ('false', fail-closed) until completed."
                ),
            }
        )
    return entries


def _column_masks(column_masks: Any, *, database: str, table: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for mask in column_masks or ():
        if not isinstance(mask, dict):
            continue
        column = str(mask.get("column") or "").strip()
        if not column:
            continue
        function = str(mask.get("function") or "")
        name = _safe_filter_name(f"{column}_mask")
        principals = _principals(mask.get("applies_to"))
        entries.append(
            {
                "create_data_cells_filter": {
                    "TableData": {
                        "TableCatalogId": _ACCOUNT_PLACEHOLDER,
                        "DatabaseName": database,
                        "TableName": table,
                        "Name": name,
                        "RowFilter": {"AllRowsWildcard": {}},
                        "ColumnWildcard": {"ExcludedColumnNames": [column]},
                    }
                },
                "grants": _data_filter_grants(principals, database=database, table=table, name=name),
                "todo": (
                    f"Lake Formation has no value-masking function (contract requested {function!r} on {column!r}). "
                    "This scaffold excludes the column for the listed principals (column-level security). To keep a "
                    "transformed value instead of hiding it, mask in the ingestion job or a consumer view."
                ),
            }
        )
    return entries


def _data_filter_grants(principals: list[str], *, database: str, table: str, name: str) -> list[dict[str, Any]]:
    return [
        {
            "Principal": {"DataLakePrincipalIdentifier": principal},
            "Resource": {
                "DataCellsFilter": {
                    "TableCatalogId": _ACCOUNT_PLACEHOLDER,
                    "DatabaseName": database,
                    "TableName": table,
                    "Name": name,
                }
            },
            "Permissions": ["SELECT"],
            "PermissionsWithGrantOption": [],
        }
        for principal in principals
    ]


def _permissions(privileges: Any) -> list[str]:
    return [str(item).strip().upper() for item in _as_list(privileges) if str(item).strip()]


def _principals(applies_to: Any) -> list[str]:
    if not isinstance(applies_to, dict):
        return []
    return [str(item).strip() for item in _as_list(applies_to.get("principals")) if str(item).strip()]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _safe_filter_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.strip())
    return cleaned.strip("_") or "filter"


def _access(contract: SemanticContract) -> dict[str, Any]:
    governance = contract.governance
    if governance is None or not governance.access:
        return {}
    return dict(governance.access)
