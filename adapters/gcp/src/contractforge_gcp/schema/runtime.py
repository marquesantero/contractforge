"""BigQuery runtime schema-policy enforcement helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from contractforge_core.schema import compare_schema, validate_schema_diff
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import identifier, quote_table_ref, target_project, target_table, target_table_id
from contractforge_gcp.rendering.sql import render_bigquery_load_job_config
from contractforge_gcp.runtime import BigQueryJobEvidence, BigQueryRuntimeClient


@dataclass(frozen=True)
class BigQuerySchemaPolicyResult:
    commands: tuple[str, ...]
    source_columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    schema_changes: dict[str, Any]
    jobs: tuple[BigQueryJobEvidence, ...]
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["jobs"] = [job.to_dict() for job in self.jobs]
        return payload


def enforce_bigquery_schema_policy(
    *,
    client: BigQueryRuntimeClient,
    contract: SemanticContract,
    environment: GCPEnvironment,
    apply_changes: bool = True,
) -> BigQuerySchemaPolicyResult:
    """Inspect BigQuery schemas, validate policy and optionally apply nullable additions."""

    source_types, source_job = source_column_types_for(client=client, contract=contract, environment=environment)
    target_types, target_job = target_column_types_for(client=client, contract=contract, environment=environment)
    jobs = [source_job, target_job]
    if not source_types:
        raise ValueError("GCP schema policy could not inspect source schema.")

    if not target_types and contract.write.mode == "scd0_overwrite":
        return BigQuerySchemaPolicyResult(
            commands=(),
            source_columns=tuple(source_types),
            target_columns=tuple(source_types),
            schema_changes=_schema_changes(
                added=(),
                removed=(),
                type_changes=(),
                source_types=source_types,
                target_types={},
                applied_additions=set(),
                warning="target_missing_initial_overwrite_create",
            ),
            jobs=tuple(jobs),
        )

    diff = compare_schema(source_types, target_types)
    schema_changes = _schema_changes(
        added=diff.added_columns,
        removed=diff.removed_columns,
        type_changes=tuple(change.as_dict() for change in diff.type_changes),
        source_types=source_types,
        target_types=target_types,
        applied_additions=set(),
        warning=None,
    )
    try:
        validate_schema_diff(diff, contract.write.schema_policy)
    except ValueError as exc:
        return BigQuerySchemaPolicyResult(
            commands=(),
            source_columns=tuple(source_types),
            target_columns=tuple(target_types),
            schema_changes=schema_changes,
            jobs=tuple(jobs),
            error_message=str(exc),
        )
    commands: list[str] = []
    applied_additions: set[str] = set()
    if apply_changes and contract.write.schema_policy in {"additive_only", "permissive"}:
        for column in diff.added_columns:
            command = _add_column_sql(target_table(contract, environment), column, source_types[column])
            apply_job = client.query(command)
            jobs.append(apply_job)
            if not apply_job.ok:
                raise ValueError(f"GCP schema policy failed to add column {column}: {apply_job.error_message}")
            commands.append(command)
            applied_additions.add(column)

    target_columns = tuple(target_types) + tuple(column for column in diff.added_columns if column in applied_additions)
    return BigQuerySchemaPolicyResult(
        commands=tuple(commands),
        source_columns=tuple(source_types),
        target_columns=target_columns,
        schema_changes=_schema_changes(
            added=diff.added_columns,
            removed=diff.removed_columns,
            type_changes=tuple(change.as_dict() for change in diff.type_changes),
            source_types=source_types,
            target_types=target_types,
            applied_additions=applied_additions,
            warning=None,
        ),
        jobs=tuple(jobs),
    )


def source_column_types_for(
    *,
    client: BigQueryRuntimeClient,
    contract: SemanticContract,
    environment: GCPEnvironment,
) -> tuple[dict[str, str], BigQueryJobEvidence]:
    source_query = _source_query(contract)
    if source_query is not None:
        return _column_types_for_query(client=client, contract=contract, environment=environment, query=source_query)
    source_load_job = _source_load_job_config(contract, environment)
    if source_load_job is not None:
        return _column_types_for_load_job(client=client, contract=contract, environment=environment, load_job_config=source_load_job)
    source_table = _source_table_ref(contract, environment)
    if source_table is None:
        raise ValueError(
            "GCP schema policy source inspection currently supports SQL, table, view and registered Iceberg table sources."
        )
    return _column_types_for_table(client=client, table_ref=source_table, fallback_project=environment.project_id)


def target_column_types_for(
    *,
    client: BigQueryRuntimeClient,
    contract: SemanticContract,
    environment: GCPEnvironment,
) -> tuple[dict[str, str], BigQueryJobEvidence]:
    return _column_types_for_table(
        client=client,
        table_ref=target_table_id(contract, environment),
        fallback_project=target_project(contract, environment) or environment.project_id,
    )


def schema_policy_job_evidence(result: BigQuerySchemaPolicyResult) -> BigQueryJobEvidence:
    last_job = result.jobs[-1] if result.jobs else None
    return BigQueryJobEvidence(
        job_id=last_job.job_id if last_job else None,
        job_type="SCHEMA_POLICY",
        state="FAILED" if result.error_message else last_job.state if last_job else "DONE",
        error_message=result.error_message or (last_job.error_message if last_job else None),
        statement_type=last_job.statement_type if last_job else "SCHEMA_POLICY",
        total_bytes_processed=sum(job.total_bytes_processed or 0 for job in result.jobs) or None,
        total_bytes_billed=sum(job.total_bytes_billed or 0 for job in result.jobs) or None,
        total_slot_ms=sum(job.total_slot_ms or 0 for job in result.jobs) or None,
        raw={"schema_policy": result.to_dict()},
    )


def _column_types_for_table(
    *,
    client: BigQueryRuntimeClient,
    table_ref: str,
    fallback_project: str | None,
) -> tuple[dict[str, str], BigQueryJobEvidence]:
    project_id, dataset, table = _split_table_ref(table_ref, fallback_project=fallback_project)
    query = (
        "SELECT column_name, data_type, is_nullable, ordinal_position "
        f"FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.COLUMNS` "
        f"WHERE table_name = '{_sql_string(table)}' "
        "ORDER BY ordinal_position"
    )
    job = client.query(query)
    if not job.ok:
        raise ValueError(f"GCP schema policy failed to inspect `{table_ref}`: {job.error_message}")
    return {_row_value(row, "column_name"): _normalize_bigquery_type(_row_value(row, "data_type")) for row in job.result_rows or ()}, job


def _column_types_for_query(
    *,
    client: BigQueryRuntimeClient,
    contract: SemanticContract,
    environment: GCPEnvironment,
    query: str,
) -> tuple[dict[str, str], BigQueryJobEvidence]:
    probe_table = _schema_probe_table(contract, environment)
    create_job = client.query(
        "CREATE OR REPLACE TABLE "
        + quote_table_ref(probe_table, environment)
        + " AS\nSELECT * FROM (\n"
        + query.rstrip().rstrip(";")
        + "\n) AS contractforge_schema_source\nWHERE FALSE"
    )
    if not create_job.ok:
        raise ValueError(f"GCP schema policy failed to create SQL source schema probe: {create_job.error_message}")
    try:
        columns, inspect_job = _column_types_for_table(
            client=client,
            table_ref=probe_table,
            fallback_project=environment.project_id,
        )
    finally:
        drop_job = client.query("DROP TABLE IF EXISTS " + quote_table_ref(probe_table, environment))
    if not drop_job.ok:
        raise ValueError(f"GCP schema policy failed to drop SQL source schema probe: {drop_job.error_message}")
    return columns, _schema_probe_job_evidence(
        create_job=create_job,
        inspect_job=inspect_job,
        drop_job=drop_job,
        statement_type="SQL_SCHEMA_PROBE",
        raw_key="sql_schema_probe",
    )


def _column_types_for_load_job(
    *,
    client: BigQueryRuntimeClient,
    contract: SemanticContract,
    environment: GCPEnvironment,
    load_job_config: dict[str, Any],
) -> tuple[dict[str, str], BigQueryJobEvidence]:
    probe_table = _schema_probe_table(contract, environment)
    declared_columns = _declared_source_columns(contract)
    create_job: BigQueryJobEvidence | None = None
    if declared_columns:
        create_job = client.query(_create_probe_table_sql(probe_table, declared_columns, environment))
        if not create_job.ok:
            raise ValueError(f"GCP schema policy failed to create source schema probe: {create_job.error_message}")
    probe_config = dict(load_job_config)
    probe_config["destination_table"] = probe_table
    probe_config["write_disposition"] = "WRITE_TRUNCATE"
    if declared_columns:
        probe_config.pop("autodetect", None)
    load_job = client.load_table_from_uri(probe_config)
    if not load_job.ok:
        raise ValueError(f"GCP schema policy failed to load source schema probe: {load_job.error_message}")
    try:
        columns, inspect_job = _column_types_for_table(
            client=client,
            table_ref=probe_table,
            fallback_project=environment.project_id,
        )
    finally:
        drop_job = client.query("DROP TABLE IF EXISTS " + quote_table_ref(probe_table, environment))
    if not drop_job.ok:
        raise ValueError(f"GCP schema policy failed to drop source schema probe: {drop_job.error_message}")
    return columns, _schema_probe_job_evidence(
        create_job=create_job,
        load_job=load_job,
        inspect_job=inspect_job,
        drop_job=drop_job,
        statement_type="LOAD_SCHEMA_PROBE",
        raw_key="load_schema_probe",
    )


def _schema_probe_job_evidence(
    *,
    create_job: BigQueryJobEvidence | None = None,
    load_job: BigQueryJobEvidence | None = None,
    inspect_job: BigQueryJobEvidence,
    drop_job: BigQueryJobEvidence,
    statement_type: str,
    raw_key: str,
) -> BigQueryJobEvidence:
    jobs = tuple(job for job in (create_job, load_job, inspect_job, drop_job) if job is not None)
    return BigQueryJobEvidence(
        job_id=inspect_job.job_id,
        job_type="QUERY",
        state="DONE" if all(job.ok for job in jobs) else "FAILED",
        error_message=next((job.error_message for job in jobs if job.error_message), None),
        statement_type=statement_type,
        total_bytes_processed=sum(job.total_bytes_processed or 0 for job in jobs) or None,
        total_bytes_billed=sum(job.total_bytes_billed or 0 for job in jobs) or None,
        total_slot_ms=sum(job.total_slot_ms or 0 for job in jobs) or None,
        raw={raw_key: [job.to_dict() for job in jobs]},
    )


def _schema_changes(
    *,
    added: tuple[str, ...],
    removed: tuple[str, ...],
    type_changes: tuple[dict[str, Any], ...],
    source_types: dict[str, str],
    target_types: dict[str, str],
    applied_additions: set[str],
    warning: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if warning:
        payload["warnings"] = (warning,)
    if added:
        payload["added_columns"] = tuple(
            {
                "column": column,
                "source_type": source_types[column],
                "target_type": None,
                "change_type": "ADD_COLUMN",
                "applied": column in applied_additions,
            }
            for column in added
        )
    if removed:
        payload["removed_columns"] = tuple(
            {
                "column": column,
                "source_type": None,
                "target_type": target_types[column],
                "change_type": "REMOVE_COLUMN",
                "applied": False,
            }
            for column in removed
        )
    if type_changes:
        payload["type_changes"] = tuple({**change, "change_type": "TYPE_CHANGE", "applied": False} for change in type_changes)
    return payload


def _source_table_ref(contract: SemanticContract, environment: GCPEnvironment) -> str | None:
    source = contract.source.raw or {}
    source_type = str(source.get("type") or source.get("connector") or "").strip().lower()
    if source_type not in {"table", "view", "iceberg_table"}:
        return None
    return str(source.get("table") or source.get("table_ref") or source.get("ref") or contract.source.location or "").strip()


def _source_query(contract: SemanticContract) -> str | None:
    source = contract.source.raw or {}
    source_type = str(source.get("type") or source.get("connector") or "").strip().lower()
    if source_type != "sql":
        return None
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    query = str(source.get("query") or options.get("query") or "").strip()
    return query or None


def _source_load_job_config(contract: SemanticContract, environment: GCPEnvironment) -> dict[str, Any] | None:
    body = render_bigquery_load_job_config(contract, environment)
    if not body:
        return None
    payload = json.loads(body)
    return payload if isinstance(payload, dict) else None


def _declared_source_columns(contract: SemanticContract) -> dict[str, str]:
    source = contract.source.raw or {}
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    for value in (read.get("schema"), read.get("columns"), source.get("schema"), source.get("columns")):
        columns = _column_type_mapping(value)
        if columns:
            return columns
    return {}


def _column_type_mapping(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(name).strip(): _normalize_bigquery_type(str(data_type or "STRING")) for name, data_type in value.items() if str(name).strip()}
    if isinstance(value, (list, tuple)):
        result: dict[str, str] = {}
        for item in value:
            if isinstance(item, str):
                name = item.strip()
                if name:
                    result[name] = "STRING"
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("column") or item.get("field") or "").strip()
                if name:
                    result[name] = _normalize_bigquery_type(str(item.get("type") or item.get("data_type") or "STRING"))
        return result
    return {}


def _create_probe_table_sql(table_ref: str, columns: dict[str, str], environment: GCPEnvironment) -> str:
    column_sql = ", ".join(f"{identifier(column)} {_normalize_bigquery_type(data_type)}" for column, data_type in columns.items())
    return f"CREATE OR REPLACE TABLE {quote_table_ref(table_ref, environment)} ({column_sql})"


def _schema_probe_table(contract: SemanticContract, environment: GCPEnvironment) -> str:
    digest = hashlib.sha1(target_table_id(contract, environment).encode("utf-8")).hexdigest()[:12]
    return f"{environment.project_id}.{environment.evidence_dataset}.cf_schema_probe_{digest}"


def _add_column_sql(table: str, column: str, data_type: str) -> str:
    return f"ALTER TABLE {table} ADD COLUMN {identifier(column)} {data_type}"


def _split_table_ref(table_ref: str, *, fallback_project: str | None) -> tuple[str, str, str]:
    ref = quote_table_ref(table_ref, GCPEnvironment(project_id=fallback_project))
    parts = ref.strip("`").split(".")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2 and fallback_project:
        return fallback_project, parts[0], parts[1]
    raise ValueError(f"GCP schema policy requires a dataset-qualified table reference: {table_ref!r}")


def _row_value(row: dict[str, Any], key: str) -> str:
    for candidate in (key, key.upper(), key.lower()):
        value = row.get(candidate)
        if value is not None:
            return str(value).strip()
    return ""


def _normalize_bigquery_type(value: str) -> str:
    aliases = {
        "BOOL": "BOOLEAN",
        "FLOAT": "FLOAT64",
        "INTEGER": "INT64",
    }
    text = value.strip().upper()
    return aliases.get(text, text)


def _sql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


__all__ = [
    "BigQuerySchemaPolicyResult",
    "enforce_bigquery_schema_policy",
    "schema_policy_job_evidence",
    "source_column_types_for",
    "target_column_types_for",
]
