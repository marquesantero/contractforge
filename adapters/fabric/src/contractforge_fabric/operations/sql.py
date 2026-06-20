"""Render Fabric operations metadata evidence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_fabric.evidence import evidence_table_names
from contractforge_fabric.naming import target_table_name
from contractforge_fabric.sql import quote_identifier, quote_table_name, sql_bool, sql_int, sql_string

_COLUMNS = [
    "run_id",
    "target_table",
    "criticality",
    "expected_frequency",
    "freshness_sla_minutes",
    "alert_on_failure",
    "alert_on_quality_fail",
    "runbook_url",
    "ownership_json",
    "owners_json",
    "groups_json",
    "tags_json",
    "status",
    "recorded_at_utc",
    "framework_version",
    "ctrl_schema_version",
]


def has_operations_metadata(contract: SemanticContract) -> bool:
    return bool(contract.operations and contract.operations.metadata)


def render_operations_json(contract: SemanticContract) -> str:
    return json.dumps(operations_payload(contract), indent=2, sort_keys=True)


def render_operations_insert_sql(
    contract: SemanticContract,
    *,
    schema: str = "contractforge",
    run_id: str = "${run_id}",
    status: str = "PLANNED",
    recorded_at_utc: datetime | None = None,
) -> str:
    if not has_operations_metadata(contract):
        return "-- No operations metadata declared.\n"
    payload = operations_payload(contract)
    table = evidence_table_names(schema)["operations"]
    recorded_at_utc = recorded_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    values = [
        sql_string(run_id),
        sql_string(target_table_name(contract)),
        sql_string(payload.get("criticality")),
        sql_string(payload.get("expected_frequency")),
        sql_int(payload.get("freshness_sla_minutes")),
        sql_bool(payload.get("alert_on_failure")),
        sql_bool(payload.get("alert_on_quality_fail")),
        sql_string(payload.get("runbook_url")),
        _json(payload.get("ownership")),
        _json(payload.get("owners")),
        _json(payload.get("groups")),
        _json(payload.get("tags")),
        sql_string(status),
        f"TIMESTAMP {sql_string(recorded_at_utc.strftime('%Y-%m-%d %H:%M:%S'))}",
        sql_string("contractforge-fabric"),
        "1",
    ]
    return (
        f"INSERT INTO {quote_table_name(table)} "
        f"({', '.join(quote_identifier(column) for column in _COLUMNS)}) "
        f"VALUES ({', '.join(values)});"
    )


def operations_payload(contract: SemanticContract) -> dict[str, Any]:
    raw = dict(contract.operations.metadata or {}) if contract.operations and contract.operations.metadata else {}
    ownership = _mapping(raw.get("ownership"))
    operations = _mapping(raw.get("operations")) or raw
    return redact_value(
        {
            "criticality": operations.get("criticality"),
            "expected_frequency": operations.get("expected_frequency"),
            "freshness_sla_minutes": operations.get("freshness_sla_minutes"),
            "alert_on_failure": bool(operations.get("alert_on_failure", False)),
            "alert_on_quality_fail": bool(operations.get("alert_on_quality_fail", False)),
            "runbook_url": operations.get("runbook_url"),
            "ownership": ownership,
            "owners": _as_list(operations.get("owners")),
            "groups": _as_list(operations.get("groups")),
            "tags": _mapping(operations.get("tags")),
        }
    )


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]  # type: ignore[union-attr]


def _json(value: object) -> str:
    return sql_string(json.dumps(value, sort_keys=True, separators=(",", ":")))
