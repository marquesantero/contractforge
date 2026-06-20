"""GCP BigQuery contract smoke workflow."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from dataclasses import asdict, dataclass
from typing import Any

from contractforge_core.connectors import http_file_format, read_http_file_payload, read_rest_api_records
from contractforge_core.connectors.api.rest.pagination import json_path
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.api import plan_gcp_contract, render_gcp_contract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.evidence import (
    render_quality_evidence_insert_sql,
    render_run_evidence_insert_sql,
    render_schema_evidence_insert_sql,
)
from contractforge_gcp.governance import has_governance_ledger_plan, render_bigquery_governance_evidence_insert_sql
from contractforge_gcp.lineage import render_openlineage_insert_sql
from contractforge_gcp.runtime import (
    BigQueryJobEvidence,
    BigQueryRuntimeClient,
    bigquery_runtime_client_from_environment,
    load_job_config_from_artifact,
    split_bigquery_script,
)
from contractforge_gcp.schema import enforce_bigquery_schema_policy, schema_policy_job_evidence
from contractforge_gcp.security import resolve_gcp_secret_placeholders


@dataclass(frozen=True)
class GCPSmokeOperation:
    name: str
    kind: str
    artifact: str
    executed: bool
    job: BigQueryJobEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["job"] = None if self.job is None else self.job.to_dict()
        return payload


@dataclass(frozen=True)
class GCPContractSmokeResult:
    status: str
    executed: bool
    planning_status: str
    operations: tuple[GCPSmokeOperation, ...]
    artifacts: tuple[str, ...]
    blockers: tuple[dict[str, str], ...] = ()
    warnings: tuple[dict[str, str], ...] = ()

    @property
    def ok(self) -> bool:
        return self.status in {"DRY_RUN", "SUCCEEDED"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ok": self.ok,
            "executed": self.executed,
            "planning_status": self.planning_status,
            "operations": [operation.to_dict() for operation in self.operations],
            "artifacts": list(self.artifacts),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
        }


def run_gcp_contract_smoke(
    contract: dict[str, Any],
    environment: GCPEnvironment | dict[str, Any] | None = None,
    *,
    client: BigQueryRuntimeClient | None = None,
    execute: bool = False,
    runtime: str = "auto",
    prepare_evidence: bool = True,
    persist_evidence: bool = True,
    run_quality: bool = True,
    enforce_schema_policy: bool = False,
    allow_review_required: bool = False,
) -> GCPContractSmokeResult:
    """Render and optionally execute a single BigQuery contract smoke."""

    env = environment if isinstance(environment, GCPEnvironment) else GCPEnvironment.from_contract(environment)
    semantic = semantic_contract_from_mapping(contract)
    planning = plan_gcp_contract(contract, environment=_environment_mapping(env))
    rendered = render_gcp_contract(contract, environment=_environment_mapping(env))
    artifacts = rendered.artifacts
    operations = _planned_operations(
        artifacts,
        contract=semantic,
        prepare_evidence=prepare_evidence,
        run_quality=run_quality,
        enforce_schema_policy=enforce_schema_policy,
    )
    blockers = tuple({"code": blocker.code, "message": blocker.message} for blocker in planning.blockers)
    warnings = tuple({"code": warning.code, "message": warning.message} for warning in planning.warnings)

    if planning.status == "UNSUPPORTED" or (planning.status == "REVIEW_REQUIRED" and not allow_review_required):
        return GCPContractSmokeResult(
            status="BLOCKED",
            executed=False,
            planning_status=planning.status,
            operations=operations,
            artifacts=tuple(sorted(artifacts)),
            blockers=blockers,
            warnings=warnings,
        )
    if not execute:
        return GCPContractSmokeResult(
            status="DRY_RUN",
            executed=False,
            planning_status=planning.status,
            operations=operations,
            artifacts=tuple(sorted(artifacts)),
            blockers=blockers,
            warnings=warnings,
        )

    runtime_client = client or bigquery_runtime_client_from_environment(env, runtime=runtime)
    executed_operations: list[GCPSmokeOperation] = []
    for operation in operations:
        try:
            job = _execute_operation(
                operation,
                artifacts[operation.artifact],
                runtime_client,
                contract=semantic,
                environment=env,
            )
        except Exception as exc:  # pragma: no cover - network/runtime failures are environment-specific.
            failed_job = BigQueryJobEvidence(
                job_id=None,
                job_type=operation.kind,
                state="FAILED",
                error_message=str(exc),
            )
            executed_operations.append(
                GCPSmokeOperation(
                    name=operation.name,
                    kind=operation.kind,
                    artifact=operation.artifact,
                    executed=True,
                    job=failed_job,
                )
            )
            return GCPContractSmokeResult(
                status="FAILED",
                executed=True,
                planning_status=planning.status,
                operations=tuple(executed_operations),
                artifacts=tuple(sorted(artifacts)),
                blockers=blockers,
                warnings=warnings,
            )
        executed_operations.append(
            GCPSmokeOperation(
                name=operation.name,
                kind=operation.kind,
                artifact=operation.artifact,
                executed=True,
                job=job,
            )
        )
        if persist_evidence:
            evidence_operations = _persist_operation_evidence(
                operation=operation,
                contract=semantic,
                environment=env,
                client=runtime_client,
                job=job,
            )
            executed_operations.extend(evidence_operations)
            evidence_failure = next((item for item in evidence_operations if item.job and not item.job.ok), None)
            if evidence_failure is not None:
                return GCPContractSmokeResult(
                    status="FAILED",
                    executed=True,
                    planning_status=planning.status,
                    operations=tuple(executed_operations),
                    artifacts=tuple(sorted(artifacts)),
                    blockers=blockers,
                    warnings=warnings,
                )
        if not job.ok:
            return GCPContractSmokeResult(
                status="FAILED",
                executed=True,
                planning_status=planning.status,
                operations=tuple(executed_operations),
                artifacts=tuple(sorted(artifacts)),
                blockers=blockers,
                warnings=warnings,
            )

    return GCPContractSmokeResult(
        status="SUCCEEDED",
        executed=True,
        planning_status=planning.status,
        operations=tuple(executed_operations),
        artifacts=tuple(sorted(artifacts)),
        blockers=blockers,
        warnings=warnings,
    )


def _planned_operations(
    artifacts: dict[str, str],
    *,
    contract: SemanticContract,
    prepare_evidence: bool,
    run_quality: bool,
    enforce_schema_policy: bool,
) -> tuple[GCPSmokeOperation, ...]:
    operations: list[GCPSmokeOperation] = []
    evidence = _first_artifact(artifacts, ".gcp.evidence_ddl.sql")
    schema_policy = _first_artifact(artifacts, ".gcp.schema_policy.json")
    source_materialization = _first_artifact(artifacts, ".gcp.source_materialization.json")
    load_job = _first_artifact(artifacts, ".gcp.load_job.json")
    write_sql = _first_artifact(artifacts, ".gcp.write.sql")
    quality_sql = _first_artifact(artifacts, ".gcp.quality.sql")
    if prepare_evidence and evidence:
        operations.append(GCPSmokeOperation("prepare_evidence", "QUERY", evidence, executed=False))
    if enforce_schema_policy and schema_policy and not _materialized_http_source(contract):
        operations.append(GCPSmokeOperation("schema_policy", "SCHEMA_POLICY", schema_policy, executed=False))
    if source_materialization:
        operations.append(GCPSmokeOperation("materialize_source", "MATERIALIZE_SOURCE", source_materialization, executed=False))
    elif load_job:
        operations.append(GCPSmokeOperation("load_source", "LOAD", load_job, executed=False))
    elif write_sql:
        operations.append(GCPSmokeOperation("write_target", "QUERY", write_sql, executed=False))
    if run_quality and quality_sql:
        operations.append(GCPSmokeOperation("quality", "QUERY", quality_sql, executed=False))
    return tuple(operations)


def _materialized_http_source(contract: SemanticContract) -> bool:
    source = contract.source.raw or {}
    source_type = str(source.get("connector") or source.get("type") or "").strip().lower()
    if source_type in {"rest_api", "api", "http_api", "http_json", "http_csv", "http_text"}:
        return True
    if source_type != "http_file":
        return False
    return _http_source_format(source) in {"avro", "csv", "json", "jsonl", "ndjson", "orc", "parquet", "text"}


def _execute_operation(
    operation: GCPSmokeOperation,
    artifact_body: str,
    client: BigQueryRuntimeClient,
    *,
    contract: SemanticContract,
    environment: GCPEnvironment,
) -> BigQueryJobEvidence:
    if operation.kind == "SCHEMA_POLICY":
        return schema_policy_job_evidence(
            enforce_bigquery_schema_policy(client=client, contract=contract, environment=environment)
        )
    if operation.kind == "MATERIALIZE_SOURCE":
        return _materialize_source_to_bigquery(
            artifact_body,
            client=client,
            contract=contract,
            environment=environment,
        )
    if operation.kind == "LOAD":
        return client.load_table_from_uri(load_job_config_from_artifact(artifact_body))
    statements = split_bigquery_script(artifact_body)
    evidence: BigQueryJobEvidence | None = None
    result_rows: list[dict[str, Any]] = []
    for statement in statements:
        evidence = client.query(statement)
        if operation.name == "quality":
            result_rows.extend(evidence.result_rows or [])
            evidence = _quality_evidence(evidence)
            if result_rows:
                evidence = replace(evidence, result_rows=list(result_rows))
        if not evidence.ok:
            return evidence
    if evidence is None:
        return BigQueryJobEvidence(job_id=None, job_type=operation.kind, state="SKIPPED")
    return evidence


def _persist_operation_evidence(
    *,
    operation: GCPSmokeOperation,
    contract: SemanticContract,
    environment: GCPEnvironment,
    client: BigQueryRuntimeClient,
    job: BigQueryJobEvidence,
) -> tuple[GCPSmokeOperation, ...]:
    if operation.name in {"load_source", "write_target", "materialize_source"}:
        run_evidence_job = client.query(
            render_run_evidence_insert_sql(environment=environment, contract=contract, job=job)
        )
        lineage_evidence_job = client.query(
            render_openlineage_insert_sql(environment=environment, contract=contract, job=job)
        )
        evidence_operations = [
            GCPSmokeOperation(
                name="persist_run_evidence",
                kind="QUERY",
                artifact="inline:gcp.run_evidence",
                executed=True,
                job=run_evidence_job,
            ),
            GCPSmokeOperation(
                name="persist_lineage_evidence",
                kind="QUERY",
                artifact="inline:gcp.lineage_evidence",
                executed=True,
                job=lineage_evidence_job,
            ),
        ]
        if has_governance_ledger_plan(contract):
            governance_evidence_job = client.query(
                render_bigquery_governance_evidence_insert_sql(environment=environment, contract=contract, job=job)
            )
            evidence_operations.append(
                GCPSmokeOperation(
                    name="persist_governance_evidence",
                    kind="QUERY",
                    artifact="inline:gcp.governance_evidence",
                    executed=True,
                    job=governance_evidence_job,
                )
            )
        return tuple(evidence_operations)
    if operation.name == "quality":
        evidence_job = client.query(
            render_quality_evidence_insert_sql(environment=environment, contract=contract, job=job)
        )
        return (
            GCPSmokeOperation(
                name="persist_quality_evidence",
                kind="QUERY",
                artifact="inline:gcp.quality_evidence",
                executed=True,
                job=evidence_job,
            ),
        )
    if operation.name == "schema_policy":
        evidence_job = client.query(
            render_schema_evidence_insert_sql(environment=environment, contract=contract, job=job)
        )
        return (
            GCPSmokeOperation(
                name="persist_schema_evidence",
                kind="QUERY",
                artifact="inline:gcp.schema_evidence",
                executed=True,
                job=evidence_job,
            ),
        )
    return ()


def _first_artifact(artifacts: dict[str, str], suffix: str) -> str | None:
    for name in sorted(artifacts):
        if name.endswith(suffix):
            return name
    return None


def _quality_evidence(evidence: BigQueryJobEvidence) -> BigQueryJobEvidence:
    for row in evidence.result_rows or []:
        if "failed_rows" not in row:
            continue
        try:
            failed_rows = int(row["failed_rows"])
        except (TypeError, ValueError):
            continue
        if failed_rows > 0:
            return replace(evidence, error_message=f"Quality query returned failed_rows={failed_rows}.")
    return evidence


def _materialize_source_to_bigquery(
    artifact_body: str,
    *,
    client: BigQueryRuntimeClient,
    contract: SemanticContract,
    environment: GCPEnvironment,
) -> BigQueryJobEvidence:
    plan = json.loads(artifact_body)
    if not isinstance(plan, dict):
        raise ValueError("GCP source materialization artifact must be a JSON object.")
    source_format = str(plan.get("source_format") or "").upper()
    suffix = _source_file_suffix(source_format)
    source = resolve_gcp_secret_placeholders(contract.source.raw or {}, project_id=environment.project_id)
    path = _write_materialized_source(source, source_format=source_format, suffix=suffix)
    try:
        load_config = {
            key: value
            for key, value in plan.items()
            if key
            in {
                "destination_table",
                "source_format",
                "write_disposition",
                "skip_leading_rows",
                "autodetect",
                "schema_fields",
            }
        }
        return client.load_table_from_file(path, load_config)
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def _write_materialized_source(source: dict[str, Any], *, source_format: str, suffix: str) -> str:
    if source_format in {"AVRO", "CSV", "ORC", "PARQUET"}:
        payload = read_http_file_payload(source)
        return _write_temp_bytes(payload, suffix=suffix)
    records = _source_records(source)
    lines = [json.dumps(record, sort_keys=True, separators=(",", ":")) for record in records]
    return _write_temp_bytes(("\n".join(lines) + ("\n" if lines else "")).encode("utf-8"), suffix=suffix)


def _source_records(source: dict[str, Any]) -> list[dict[str, Any]]:
    source_type = str(source.get("connector") or source.get("type") or "").strip().lower()
    if source_type in {"rest_api", "api", "http_api"}:
        return read_rest_api_records(source)
    if source_type == "http_text" or (source_type == "http_file" and _http_source_format(source) == "text"):
        raw = read_http_file_payload(source).decode("utf-8")
        column = _http_text_column(source)
        return [{column: line} for line in raw.splitlines()]
    payload = json.loads(read_http_file_payload(source).decode("utf-8") or "null")
    records_path = _http_records_path(source)
    if records_path:
        payload = json_path(payload, records_path)
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item if isinstance(item, dict) else {"value": item} for item in payload]
    if isinstance(payload, dict):
        return [payload]
    return [{"value": payload}]


def _http_text_column(source: dict[str, Any]) -> str:
    response = source.get("response") if isinstance(source.get("response"), dict) else {}
    raw_column = str(response.get("raw_column") or "").strip()
    if raw_column:
        return raw_column
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    columns = read.get("columns")
    if isinstance(columns, str) and columns.strip():
        return columns.strip().split(",", 1)[0].strip() or "value"
    if isinstance(columns, (list, tuple)):
        for column in columns:
            if isinstance(column, dict):
                name = str(column.get("name") or column.get("column") or column.get("field") or "").strip()
            else:
                name = str(column).strip()
            if name:
                return name
    return "value"


def _http_records_path(source: dict[str, Any]) -> str:
    response = source.get("response") if isinstance(source.get("response"), dict) else {}
    return str(response.get("records_path") or "").strip()


def _http_source_format(source: dict[str, Any]) -> str:
    try:
        return str(http_file_format(source)).strip().lower()
    except Exception:
        response = source.get("response") if isinstance(source.get("response"), dict) else {}
        return str(source.get("format") or response.get("format") or "").strip().lower()


def _source_file_suffix(source_format: str) -> str:
    return {
        "AVRO": ".avro",
        "CSV": ".csv",
        "ORC": ".orc",
        "PARQUET": ".parquet",
    }.get(source_format.upper(), ".ndjson")


def _write_temp_bytes(payload: bytes, *, suffix: str) -> str:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        handle.write(payload)
        return handle.name
    finally:
        handle.close()


def _environment_mapping(environment: GCPEnvironment) -> dict[str, Any]:
    return {
        "parameters": {
            "gcp": {
                "project_id": environment.project_id,
                "location": environment.location,
                "dataset": environment.dataset,
                "staging_bucket": environment.staging_bucket,
                "service_account": environment.service_account,
            }
        },
        "evidence": {"dataset": environment.evidence_dataset},
    }


def smoke_result_json(result: GCPContractSmokeResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True)
