"""Render BigQuery table and column annotation artifacts."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import evidence_dataset, identifier, table_prefix, target_table, target_table_id


def has_annotations(contract: SemanticContract) -> bool:
    return bool(annotation_steps(contract))


def render_bigquery_annotations_sql(contract: SemanticContract, environment: GCPEnvironment) -> str:
    statements = [step["sql"] for step in annotation_steps(contract, environment=environment) if step["sql"]]
    if not statements:
        return "-- No BigQuery-native annotation intent declared.\n"
    return "\n\n".join(statements) + "\n"


def render_bigquery_annotations_plan(contract: SemanticContract, environment: GCPEnvironment) -> str:
    plan = annotations_plan(contract, environment=environment)
    if not plan["changes"]:
        return ""
    return json.dumps(plan, indent=2, sort_keys=True)


def render_bigquery_annotations_evidence_sql(
    contract: SemanticContract,
    environment: GCPEnvironment,
    *,
    run_id: str = "${run_id}",
    captured_at_utc: datetime | None = None,
) -> str:
    rows = _annotation_evidence_rows(contract, environment, run_id=run_id, captured_at_utc=captured_at_utc)
    if not rows:
        return "-- No BigQuery-native annotation intent declared.\n"
    table = f"`{table_prefix(environment.project_id, evidence_dataset(contract, environment))}.contractforge_annotation_evidence`"
    return _insert_many(table, rows)


def annotations_plan(contract: SemanticContract, environment: GCPEnvironment) -> dict[str, Any]:
    changes = annotation_steps(contract, environment=environment)
    unsupported = unsupported_annotation_steps(contract)
    return {
        "adapter": "gcp",
        "target": target_table_id(contract, environment),
        "status": "PLANNED" if changes else "NOOP",
        "apply_surface": "BigQuery table and column OPTIONS(description)",
        "apply_mode": "sql",
        "changes": changes,
        "review_required": unsupported,
    }


def annotation_steps(contract: SemanticContract, environment: GCPEnvironment | None = None) -> list[dict[str, Any]]:
    annotations = contract.governance.annotations if contract.governance else None
    if not isinstance(annotations, dict):
        return []
    env = environment or GCPEnvironment()
    table = target_table(contract, env)
    rows = []
    table_annotations = _mapping(annotations.get("table"))
    description = table_annotations.get("description")
    if description:
        value = str(redact_value(str(description)))
        rows.append(
            _change(
                scope="table",
                column=None,
                value=value,
                sql=f"ALTER TABLE {table}\nSET OPTIONS (description = {_string(value)});",
            )
        )
    for column, config in _mapping(annotations.get("columns")).items():
        data = _mapping(config)
        column_description = data.get("description")
        if column_description:
            value = str(redact_value(str(column_description)))
            rows.append(
                _change(
                    scope="column",
                    column=str(column),
                    value=value,
                    sql=f"ALTER TABLE {table}\nALTER COLUMN {identifier(str(column))}\nSET OPTIONS (description = {_string(value)});",
                )
            )
    return rows


def _annotation_evidence_rows(
    contract: SemanticContract,
    environment: GCPEnvironment,
    *,
    run_id: str,
    captured_at_utc: datetime | None,
) -> list[dict[str, Any]]:
    captured = captured_at_utc or datetime(1970, 1, 1, 0, 0, 0)
    return [
        {
            "run_id": run_id,
            "contract_name": contract.target.name,
            "target_table": target_table_id(contract, environment),
            "annotation_scope": step["annotation_scope"],
            "annotation_type": step["annotation_type"],
            "column_name": step["column_name"],
            "key": step["key"],
            "value": step["value"],
            "status": "PLANNED",
            "error_message": None,
            "applied_sql": step["sql"],
            "annotation_ts": captured,
            "annotation_date": captured.date(),
            "framework_version": "contractforge-gcp",
            "ctrl_schema_version": 1,
        }
        for step in annotation_steps(contract, environment)
    ]


def unsupported_annotation_steps(contract: SemanticContract) -> list[dict[str, Any]]:
    annotations = contract.governance.annotations if contract.governance else None
    if not isinstance(annotations, dict):
        return []
    rows = []
    table = _mapping(annotations.get("table"))
    rows.extend(_unsupported_tags(scope="table", column=None, data=table))
    for column, config in _mapping(annotations.get("columns")).items():
        rows.extend(_unsupported_tags(scope="column", column=str(column), data=_mapping(config)))
    return rows


def _change(*, scope: str, column: str | None, value: str, sql: str) -> dict[str, Any]:
    return {
        "annotation_scope": scope,
        "annotation_type": "description",
        "column_name": column,
        "key": "description",
        "value": value,
        "status": "PLANNED",
        "sql": sql,
    }


def _unsupported_tags(*, scope: str, column: str | None, data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in ("aliases", "tags", "deprecated", "pii"):
        if data.get(key):
            rows.append(
                {
                    "annotation_scope": scope,
                    "annotation_type": key,
                    "column_name": column,
                    "status": "REVIEW_REQUIRED",
                    "reason": "BigQuery description metadata is native; aliases, tags, lifecycle and PII metadata require a Dataplex/Knowledge Catalog policy decision.",
                }
            )
    return rows


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _insert_many(table: str, rows: list[dict[str, Any]]) -> str:
    names = tuple(rows[0])
    columns = ", ".join(identifier(name) for name in names)
    values = ",\n  ".join("(" + ", ".join(_literal(row.get(name)) for name in names) + ")" for row in rows)
    return f"INSERT INTO {table} ({columns}) VALUES\n  {values};\n"


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP {_string(value.strftime('%Y-%m-%d %H:%M:%S'))}"
    if isinstance(value, date):
        return f"DATE {_string(value.strftime('%Y-%m-%d'))}"
    return _string(str(redact_value(value)))


def _string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
        .replace("'", "\\'")
    )
    return "'" + escaped + "'"
