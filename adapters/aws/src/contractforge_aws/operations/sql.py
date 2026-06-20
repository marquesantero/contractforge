"""Render AWS operations metadata evidence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names
from contractforge_aws.rendering.names import iceberg_table_name

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


def render_operations_json(contract: SemanticContract) -> str:
    """Render normalized operations metadata as portable JSON."""

    return json.dumps(_operations_payload(contract), indent=2, sort_keys=True)


def has_operations_metadata(contract: SemanticContract) -> bool:
    return bool(contract.operations and contract.operations.metadata)


def render_operations_insert_sql(
    contract: SemanticContract,
    *,
    database: str,
    run_id: str = "${run_id}",
    status: str = "PLANNED",
    recorded_at_utc: datetime | None = None,
) -> str:
    """Render an Iceberg insert for ``ctrl_ingestion_operations``."""

    if not has_operations_metadata(contract):
        return "-- No operations metadata declared.\n"
    payload = _operations_payload(contract)
    table = evidence_table_names(database)["operations"]
    recorded_at_utc = recorded_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    values = [
        _string(run_id),
        _string(iceberg_table_name(contract)),
        _string(payload.get("criticality")),
        _string(payload.get("expected_frequency")),
        _int(payload.get("freshness_sla_minutes")),
        _bool(payload.get("alert_on_failure")),
        _bool(payload.get("alert_on_quality_fail")),
        _string(payload.get("runbook_url")),
        _json(payload.get("ownership")),
        _json(payload.get("owners")),
        _json(payload.get("groups")),
        _json(payload.get("tags")),
        _string(status),
        f"TIMESTAMP {_string(recorded_at_utc.strftime('%Y-%m-%d %H:%M:%S'))}",
        _string("contractforge-aws"),
        "1",
    ]
    return f"INSERT INTO {table} ({', '.join(_quote_identifier(column) for column in _COLUMNS)}) VALUES ({', '.join(values)});"


def _operations_payload(contract: SemanticContract) -> dict[str, Any]:
    raw = dict(contract.operations.metadata or {}) if contract.operations and contract.operations.metadata else {}
    ownership = _mapping(raw.get("ownership"))
    operations = _mapping(raw.get("operations")) or raw
    return {
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


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]  # type: ignore[union-attr]


def _json(value: object) -> str:
    return _string(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _string(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _int(value: object) -> str:
    return "NULL" if value is None else str(int(value))


def _bool(value: object) -> str:
    return "TRUE" if bool(value) else "FALSE"


def _quote_identifier(value: str) -> str:
    return f"`{value.replace('`', '``')}`"
