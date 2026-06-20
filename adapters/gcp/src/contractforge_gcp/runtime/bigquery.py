"""BigQuery runtime helpers for GCP smoke execution."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Protocol

from contractforge_gcp.environment import GCPEnvironment


@dataclass(frozen=True)
class BigQueryJobEvidence:
    job_id: str | None
    job_type: str
    state: str | None = None
    started_at_ms: int | None = None
    finished_at_ms: int | None = None
    error_message: str | None = None
    statement_type: str | None = None
    total_bytes_processed: int | None = None
    total_bytes_billed: int | None = None
    total_slot_ms: int | None = None
    inserted_rows: int | None = None
    updated_rows: int | None = None
    deleted_rows: int | None = None
    output_rows: int | None = None
    result_rows: list[dict[str, Any]] | None = None
    raw: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.error_message in (None, "")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BigQueryRuntimeClient(Protocol):
    def query(self, sql: str) -> BigQueryJobEvidence:
        ...

    def load_table_from_uri(self, load_job_config: dict[str, Any]) -> BigQueryJobEvidence:
        ...

    def load_table_from_file(self, path: str, load_job_config: dict[str, Any]) -> BigQueryJobEvidence:
        ...


class GoogleCloudBigQueryClient:
    """Small lazy wrapper around `google-cloud-bigquery`."""

    def __init__(self, environment: GCPEnvironment) -> None:
        try:
            from google.cloud import bigquery
        except ImportError as exc:  # pragma: no cover - exercised only without runtime extra.
            raise RuntimeError(
                "GCP smoke execution requires `google-cloud-bigquery`. "
                "Install the adapter with the `runtime` extra before using --execute."
            ) from exc

        self._bigquery = bigquery
        self._location = environment.location
        self._client = bigquery.Client(project=environment.project_id)

    def query(self, sql: str) -> BigQueryJobEvidence:
        job = self._client.query(sql, location=self._location)
        rows = [dict(row.items()) for row in job.result()]
        evidence = bigquery_job_evidence(job, job_type="QUERY")
        return BigQueryJobEvidence(**{**evidence.to_dict(), "result_rows": rows})

    def load_table_from_uri(self, load_job_config: dict[str, Any]) -> BigQueryJobEvidence:
        job_config = self._load_job_config(load_job_config)
        source_uris = load_job_config.get("source_uris") or load_job_config.get("sourceUris")
        destination = load_job_config["destination_table"]
        job = self._client.load_table_from_uri(source_uris, destination, job_config=job_config, location=self._location)
        job.result()
        return bigquery_job_evidence(job, job_type="LOAD")

    def load_table_from_file(self, path: str, load_job_config: dict[str, Any]) -> BigQueryJobEvidence:
        job_config = self._load_job_config(load_job_config)
        destination = load_job_config["destination_table"]
        with open(path, "rb") as handle:
            job = self._client.load_table_from_file(handle, destination, job_config=job_config, location=self._location)
            job.result()
        return bigquery_job_evidence(job, job_type="LOAD")

    def _load_job_config(self, payload: dict[str, Any]):
        source_format = payload.get("source_format") or payload.get("sourceFormat")
        write_disposition = payload.get("write_disposition") or payload.get("writeDisposition")
        config = self._bigquery.LoadJobConfig(
            source_format=getattr(self._bigquery.SourceFormat, str(source_format)),
            write_disposition=getattr(self._bigquery.WriteDisposition, str(write_disposition)),
        )
        if "skip_leading_rows" in payload:
            config.skip_leading_rows = int(payload["skip_leading_rows"])
        if "autodetect" in payload:
            config.autodetect = bool(payload["autodetect"])
        if "schema_fields" in payload:
            config.schema = [
                self._bigquery.SchemaField(str(field["name"]), str(field["type"]))
                for field in payload["schema_fields"]
                if isinstance(field, dict) and field.get("name")
            ]
        return config


class BqCliBigQueryClient:
    """BigQuery runtime client backed by the Cloud SDK `bq` command."""

    def __init__(self, environment: GCPEnvironment) -> None:
        bq_path = shutil.which("bq")
        if bq_path is None:
            raise RuntimeError("GCP smoke execution with runtime=bq requires the `bq` CLI on PATH.")
        if not environment.project_id:
            raise ValueError("GCP BigQuery CLI smoke requires environment.parameters.gcp.project_id.")
        self._bq_path = bq_path
        self._project_id = environment.project_id
        self._location = environment.location or "US"

    def query(self, sql: str) -> BigQueryJobEvidence:
        job_id = _new_job_id("query")
        command = self._base_command() + [
            "query",
            "--use_legacy_sql=false",
            f"--job_id={job_id}",
            _bq_sql_argument(sql),
        ]
        completed = _run_bq(command)
        if completed.returncode != 0:
            return BigQueryJobEvidence(
                job_id=job_id,
                job_type="QUERY",
                state="FAILED",
                error_message=_command_error(completed),
                raw={"stderr": completed.stderr, "stdout": completed.stdout},
            )
        return self._job_evidence(job_id, job_type="QUERY", result_rows=_json_rows(completed.stdout))

    def load_table_from_uri(self, load_job_config: dict[str, Any]) -> BigQueryJobEvidence:
        job_id = _new_job_id("load")
        source_uris = load_job_config.get("source_uris") or load_job_config.get("sourceUris")
        if isinstance(source_uris, str):
            source_uri_arg = source_uris
        else:
            source_uri_arg = ",".join(str(item) for item in source_uris)
        return self._load_table(job_id=job_id, load_job_config=load_job_config, source_arg=source_uri_arg)

    def load_table_from_file(self, path: str, load_job_config: dict[str, Any]) -> BigQueryJobEvidence:
        job_id = _new_job_id("load_file")
        return self._load_table(job_id=job_id, load_job_config=load_job_config, source_arg=path)

    def _load_table(
        self,
        *,
        job_id: str,
        load_job_config: dict[str, Any],
        source_arg: str,
    ) -> BigQueryJobEvidence:
        command = self._base_command() + [
            "load",
            f"--job_id={job_id}",
            f"--source_format={load_job_config['source_format']}",
        ]
        if load_job_config.get("write_disposition") == "WRITE_TRUNCATE":
            command.append("--replace")
        if "skip_leading_rows" in load_job_config:
            command.append(f"--skip_leading_rows={load_job_config['skip_leading_rows']}")
        if load_job_config.get("autodetect") is True:
            command.append("--autodetect")
        command.extend([_bq_destination_table(str(load_job_config["destination_table"])), source_arg])
        schema_argument = _bq_schema_argument(load_job_config.get("schema_fields"))
        if schema_argument:
            command.append(schema_argument)
        completed = _run_bq(command)
        if completed.returncode != 0:
            return BigQueryJobEvidence(
                job_id=job_id,
                job_type="LOAD",
                state="FAILED",
                error_message=_command_error(completed),
                raw={"stderr": completed.stderr, "stdout": completed.stdout},
            )
        return self._job_evidence(job_id, job_type="LOAD")

    def _base_command(self) -> list[str]:
        return [
            self._bq_path,
            f"--project_id={self._project_id}",
            f"--location={self._location}",
            "--format=prettyjson",
        ]

    def _job_evidence(
        self,
        job_id: str,
        *,
        job_type: str,
        result_rows: list[dict[str, Any]] | None = None,
    ) -> BigQueryJobEvidence:
        completed = _run_bq(self._base_command() + ["show", "-j", job_id])
        if completed.returncode != 0:
            return BigQueryJobEvidence(
                job_id=job_id,
                job_type=job_type,
                state="UNKNOWN",
                error_message=_command_error(completed),
                raw={"stderr": completed.stderr, "stdout": completed.stdout},
            )
        payload = json.loads(completed.stdout or "{}")
        return bigquery_job_evidence_from_resource(payload, job_type=job_type, result_rows=result_rows)


def bigquery_runtime_client_from_environment(
    environment: GCPEnvironment,
    *,
    runtime: str = "auto",
) -> BigQueryRuntimeClient:
    if runtime == "bq":
        return BqCliBigQueryClient(environment)
    if runtime == "python":
        return GoogleCloudBigQueryClient(environment)
    if runtime != "auto":
        raise ValueError("runtime must be one of: auto, bq, python")
    if shutil.which("bq") is not None:
        return BqCliBigQueryClient(environment)
    return GoogleCloudBigQueryClient(environment)


def bigquery_job_evidence(job: Any, *, job_type: str) -> BigQueryJobEvidence:
    dml_stats = getattr(job, "dml_stats", None)
    raw = _job_raw(job)
    return BigQueryJobEvidence(
        job_id=_string(getattr(job, "job_id", None)),
        job_type=job_type,
        state=_string(getattr(job, "state", None)),
        started_at_ms=_datetime_ms(getattr(job, "started", None)) or _statistics_ms(raw, "startTime"),
        finished_at_ms=_datetime_ms(getattr(job, "ended", None)) or _statistics_ms(raw, "endTime"),
        error_message=_job_error_message(job),
        statement_type=_string(getattr(job, "statement_type", None)),
        total_bytes_processed=_int_or_none(getattr(job, "total_bytes_processed", None)),
        total_bytes_billed=_int_or_none(getattr(job, "total_bytes_billed", None)),
        total_slot_ms=_int_or_none(getattr(job, "slot_millis", None) or getattr(job, "total_slot_ms", None)),
        inserted_rows=_int_or_none(getattr(dml_stats, "inserted_row_count", None)),
        updated_rows=_int_or_none(getattr(dml_stats, "updated_row_count", None)),
        deleted_rows=_int_or_none(getattr(dml_stats, "deleted_row_count", None)),
        output_rows=_int_or_none(getattr(job, "output_rows", None)),
        raw=raw,
    )


def bigquery_job_evidence_from_resource(
    payload: dict[str, Any],
    *,
    job_type: str,
    result_rows: list[dict[str, Any]] | None = None,
) -> BigQueryJobEvidence:
    job_ref = payload.get("jobReference") if isinstance(payload.get("jobReference"), dict) else {}
    status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
    statistics = payload.get("statistics") if isinstance(payload.get("statistics"), dict) else {}
    query_stats = statistics.get("query") if isinstance(statistics.get("query"), dict) else {}
    load_stats = statistics.get("load") if isinstance(statistics.get("load"), dict) else {}
    dml_stats = query_stats.get("dmlStats") if isinstance(query_stats.get("dmlStats"), dict) else {}
    error = status.get("errorResult") if isinstance(status.get("errorResult"), dict) else None
    return BigQueryJobEvidence(
        job_id=_string(job_ref.get("jobId") or payload.get("id")),
        job_type=job_type,
        state=_string(status.get("state")),
        started_at_ms=_int_or_none(statistics.get("startTime")),
        finished_at_ms=_int_or_none(statistics.get("endTime")),
        error_message=None if error is None else _string(error.get("message") or error.get("reason")),
        statement_type=_string(query_stats.get("statementType")),
        total_bytes_processed=_int_or_none(query_stats.get("totalBytesProcessed") or statistics.get("totalBytesProcessed")),
        total_bytes_billed=_int_or_none(query_stats.get("totalBytesBilled")),
        total_slot_ms=_int_or_none(query_stats.get("totalSlotMs") or statistics.get("totalSlotMs")),
        inserted_rows=_int_or_none(dml_stats.get("insertedRowCount")),
        updated_rows=_int_or_none(dml_stats.get("updatedRowCount")),
        deleted_rows=_int_or_none(dml_stats.get("deletedRowCount")),
        output_rows=_int_or_none(load_stats.get("outputRows")),
        result_rows=result_rows,
        raw=_redacted_job_payload(payload),
    )


def load_job_config_from_artifact(body: str) -> dict[str, Any]:
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("BigQuery load job artifact must be a JSON object.")
    if not payload.get("source_uris"):
        raise ValueError("BigQuery load job artifact requires source_uris.")
    if not payload.get("destination_table"):
        raise ValueError("BigQuery load job artifact requires destination_table.")
    return payload


def split_bigquery_script(sql: str) -> tuple[str, ...]:
    """Split generated BigQuery SQL artifacts into executable statements."""

    statements = [_strip_sql_comments(item.strip()) for item in sql.split(";")]
    return tuple(statement for statement in statements if statement)


def _job_error_message(job: Any) -> str | None:
    error = getattr(job, "error_result", None)
    if isinstance(error, dict):
        return _string(error.get("message") or error.get("reason"))
    return _string(error)


def _strip_sql_comments(statement: str) -> str:
    lines = [line for line in statement.splitlines() if not line.strip().startswith("--")]
    return "\n".join(lines).strip()


def _job_raw(job: Any) -> dict[str, Any] | None:
    properties = getattr(job, "_properties", None)
    return properties if isinstance(properties, dict) else None


def _statistics_ms(raw: dict[str, Any] | None, key: str) -> int | None:
    if not isinstance(raw, dict):
        return None
    statistics = raw.get("statistics") if isinstance(raw.get("statistics"), dict) else {}
    return _int_or_none(statistics.get(key))


def _datetime_ms(value: Any) -> int | None:
    if not isinstance(value, datetime):
        return None
    return int(value.timestamp() * 1000)


def _run_bq(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _new_job_id(kind: str) -> str:
    return f"cf_gcp_smoke_{kind}_{uuid.uuid4().hex[:20]}"


def _command_error(completed: subprocess.CompletedProcess[str]) -> str:
    return (completed.stderr or completed.stdout or f"bq exited with code {completed.returncode}").strip()


def _bq_sql_argument(sql: str) -> str:
    return " ".join(line.strip() for line in sql.splitlines() if line.strip())


def _bq_destination_table(table_id: str) -> str:
    parts = table_id.split(".")
    if len(parts) == 3:
        return f"{parts[0]}:{parts[1]}.{parts[2]}"
    return table_id


def _bq_schema_argument(value: Any) -> str:
    if not isinstance(value, (list, tuple)):
        return ""
    fields: list[str] = []
    for item in value:
        if isinstance(item, dict) and item.get("name"):
            fields.append(f"{item['name']}:{item.get('type') or 'STRING'}")
    return ",".join(fields)


def _json_rows(value: str) -> list[dict[str, Any]] | None:
    try:
        payload = json.loads(value or "[]")
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    rows = [item for item in payload if isinstance(item, dict)]
    return rows


def _redacted_job_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = _redact_value(payload)
    return redacted if isinstance(redacted, dict) else {}


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"principal_subject", "user_email"}:
                result[key] = "REDACTED"
            else:
                result[key] = _redact_value(item)
        return result
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
