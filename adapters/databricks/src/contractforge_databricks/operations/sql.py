"""Render Databricks operations metadata evidence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.coercion import mapping, string_list
from contractforge_databricks.evidence.tables import evidence_table_names
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_table_name, sql_int, sql_string

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
]


def render_operations_json(contract: SemanticContract) -> str:
    return json.dumps(_operations_payload(contract), indent=2, sort_keys=True)


def has_operations_metadata(contract: SemanticContract) -> bool:
    return bool(contract.operations and contract.operations.metadata)


def render_operations_insert_sql(
    contract: SemanticContract,
    *,
    run_id: str = "${run_id}",
    status: str = "PLANNED",
    recorded_at_utc: datetime | None = None,
    catalog: str = "main",
    schema: str = "ops",
) -> str:
    payload = _operations_payload(contract)
    table = evidence_table_names(catalog, schema)["operations"]
    recorded_at_utc = recorded_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    values = [
        sql_string(run_id),
        sql_string(target_full_name(contract)),
        sql_string(payload.get("criticality")),
        sql_string(payload.get("expected_frequency")),
        sql_int(payload.get("freshness_sla_minutes")),
        _sql_bool(payload.get("alert_on_failure")),
        _sql_bool(payload.get("alert_on_quality_fail")),
        sql_string(payload.get("runbook_url")),
        _json(payload.get("ownership")),
        _json(payload.get("owners")),
        _json(payload.get("groups")),
        _json(payload.get("tags")),
        sql_string(status),
        f"TIMESTAMP {sql_string(recorded_at_utc.strftime('%Y-%m-%d %H:%M:%S'))}",
    ]
    return f"INSERT INTO {quote_table_name(table)} ({', '.join(_COLUMNS)}) VALUES ({', '.join(values)})"


def _operations_payload(contract: SemanticContract) -> dict[str, Any]:
    raw = contract.operations.metadata if contract.operations and contract.operations.metadata else {}
    ownership = mapping(raw.get("ownership"))
    operations = mapping(raw.get("operations")) or raw
    return {
        "criticality": operations.get("criticality"),
        "expected_frequency": operations.get("expected_frequency"),
        "freshness_sla_minutes": operations.get("freshness_sla_minutes"),
        "alert_on_failure": bool(operations.get("alert_on_failure", False)),
        "alert_on_quality_fail": bool(operations.get("alert_on_quality_fail", False)),
        "runbook_url": operations.get("runbook_url"),
        "ownership": ownership,
        "owners": string_list(operations.get("owners"), sep="|"),
        "groups": string_list(operations.get("groups"), sep="|"),
        "tags": mapping(operations.get("tags")),
    }


def _json(value: object) -> str:
    return sql_string(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _sql_bool(value: object) -> str:
    return "true" if bool(value) else "false"
