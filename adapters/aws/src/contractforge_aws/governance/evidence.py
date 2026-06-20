"""Render Lake Formation governance evidence SQL."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from functools import singledispatch
from typing import Any, Callable

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names
from contractforge_aws.governance.lakeformation import render_lake_formation_plan
from contractforge_aws.rendering.names import iceberg_table_name


@dataclass(frozen=True)
class _FilterEvidenceMapping:
    access_type: str
    matches: Callable[[dict[str, Any]], bool]
    column_names: Callable[[dict[str, Any]], list[str]]


_FILTER_EVIDENCE_MAPPINGS: tuple[_FilterEvidenceMapping, ...] = (
    _FilterEvidenceMapping(
        access_type="column_mask",
        matches=lambda table_data: "ExcludedColumnNames" in table_data.get("ColumnWildcard", {}),
        column_names=lambda table_data: table_data.get("ColumnWildcard", {}).get("ExcludedColumnNames", []),
    ),
    _FilterEvidenceMapping(
        access_type="row_filter",
        matches=lambda table_data: True,
        column_names=lambda table_data: [],
    ),
)


def render_lake_formation_evidence_sql(
    contract: SemanticContract,
    *,
    database: str,
    run_id: str = "${run_id}",
    captured_at_utc: datetime | None = None,
) -> str:
    plan = render_lake_formation_plan(contract)
    if not plan.get("permissions") and not plan.get("data_cells_filters"):
        return "-- No Lake Formation access intent declared.\n"
    captured_at_utc = captured_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    table = evidence_table_names(database)["access"]
    target = iceberg_table_name(contract)
    rows = [
        *_grant_rows(plan.get("permissions", ()), run_id=run_id, target=target, captured_at_utc=captured_at_utc),
        *_filter_rows(plan.get("data_cells_filters", ()), run_id=run_id, target=target, captured_at_utc=captured_at_utc),
    ]
    return "\n".join(_insert(table, row) for row in rows) + "\n"


def _grant_rows(
    permissions: Any,
    *,
    run_id: str,
    target: str,
    captured_at_utc: datetime,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request in permissions or ():
        principal = request.get("Principal", {}).get("DataLakePrincipalIdentifier")
        privileges = request.get("Permissions") or []
        rows.append(
            {
                "run_id": run_id,
                "target_table": target,
                "action": "grant_permissions",
                "access_type": "grant",
                "principal": principal,
                "privilege": "|".join(str(item) for item in privileges),
                "status": "PLANNED",
                "applied_sql": "lakeformation:GrantPermissions",
                "new_value": "|".join(str(item) for item in privileges),
                "payload_json": request,
                "applied_at_utc": captured_at_utc,
                "access_ts_utc": captured_at_utc,
                "access_date": captured_at_utc.date(),
                "framework_version": "contractforge-aws",
                "ctrl_schema_version": 1,
            }
        )
    return rows


def _filter_rows(
    filters: Any,
    *,
    run_id: str,
    target: str,
    captured_at_utc: datetime,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in filters or ():
        table_data = entry.get("create_data_cells_filter", {}).get("TableData", {})
        filter_name = table_data.get("Name")
        mapping = _filter_mapping(table_data)
        rows.append(
            {
                "run_id": run_id,
                "target_table": target,
                "action": "create_data_cells_filter",
                "access_type": mapping.access_type,
                "principal": "|".join(_principals(entry.get("grants"))),
                "privilege": "SELECT",
                "column_name": "|".join(mapping.column_names(table_data)),
                "object_name": filter_name,
                "status": "REVIEW_REQUIRED",
                "error_message": entry.get("todo"),
                "applied_sql": "lakeformation:CreateDataCellsFilter",
                "new_value": filter_name,
                "payload_json": entry,
                "applied_at_utc": captured_at_utc,
                "access_ts_utc": captured_at_utc,
                "access_date": captured_at_utc.date(),
                "framework_version": "contractforge-aws",
                "ctrl_schema_version": 1,
            }
        )
    return rows


def _filter_mapping(table_data: dict[str, Any]) -> _FilterEvidenceMapping:
    return next(mapping for mapping in _FILTER_EVIDENCE_MAPPINGS if mapping.matches(table_data))


def _principals(grants: Any) -> list[str]:
    return [
        str(grant.get("Principal", {}).get("DataLakePrincipalIdentifier"))
        for grant in grants or ()
        if grant.get("Principal", {}).get("DataLakePrincipalIdentifier")
    ]


def _insert(table: str, columns: dict[str, Any]) -> str:
    filtered = {key: value for key, value in columns.items() if value is not None}
    names = ", ".join(_quote_identifier(name) for name in filtered)
    values = ", ".join(_literal(value) for value in filtered.values())
    return f"INSERT INTO {table} ({names}) VALUES ({values});"


@singledispatch
def _literal(value: Any) -> str:
    return _string(str(redact_value(value)))


@_literal.register(type(None))
def _literal_none(value: None) -> str:
    return "NULL"


@_literal.register(bool)
def _literal_bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


@_literal.register(int)
@_literal.register(float)
def _literal_number(value: int | float) -> str:
    return str(value)


@_literal.register(datetime)
def _literal_datetime(value: datetime) -> str:
    return f"TIMESTAMP {_string(value.strftime('%Y-%m-%d %H:%M:%S'))}"


@_literal.register(date)
def _literal_date(value: date) -> str:
    return f"DATE {_string(value.strftime('%Y-%m-%d'))}"


@_literal.register(dict)
def _literal_dict(value: dict[str, Any]) -> str:
    return _string(json.dumps(redact_value(value), sort_keys=True, separators=(",", ":")))


def _string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_identifier(value: str) -> str:
    return f"`{str(value).replace('`', '``')}`"
