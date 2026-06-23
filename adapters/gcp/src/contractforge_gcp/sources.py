"""Google Cloud source connector classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.connectors import http_file_format, is_http_file_source, is_rest_api_connector
from contractforge_core.connectors.registry import CONNECTOR_CATALOG
from contractforge_gcp.security import has_secret_placeholders

SUPPORTED = "SUPPORTED"
SUPPORTED_WITH_WARNINGS = "SUPPORTED_WITH_WARNINGS"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
UNSUPPORTED = "UNSUPPORTED"

_CATALOG_SOURCES = frozenset({"table", "view", "sql"})
_BIGQUERY_LOAD_FORMATS = frozenset({"avro", "csv", "json", "jsonl", "ndjson", "orc", "parquet"})
_OBJECT_STORAGE_SOURCES = frozenset({"gcs", "blob", "object_storage"})
_REVIEW_SOURCES = {
    "bigquery_jdbc": "BigQuery-to-BigQuery JDBC is not the stable path; use table/view/sql sources or a reviewed external connection design.",
    "custom_transform": "Custom treatment boundaries need a reviewed BigQuery/Dataflow/Dataproc runtime binding before BigQuery runtime support.",
    "db2": "JDBC reads should be handled through Dataflow, Dataproc or a reviewed BigQuery external connection design.",
    "delta": "Path-based Delta files need a Dataproc/Spark, BigLake handoff or staged copy design before BigQuery runtime support.",
    "delta_share": "BigQuery needs a governed handoff, BigLake/external table design or a staged copy before runtime support.",
    "delta_table": "Registered Delta table references need a reviewed BigLake/external table or staged copy design before BigQuery runtime support.",
    "incremental_files": "Incremental file discovery needs Dataflow, Dataproc or adapter-managed state validation.",
    "jdbc": "JDBC reads should be handled through Dataflow, Dataproc or a reviewed BigQuery external connection design.",
    "mariadb": "JDBC reads should be handled through Dataflow, Dataproc or a reviewed BigQuery external connection design.",
    "postgres": "JDBC reads should be handled through Dataflow, Dataproc or a reviewed BigQuery external connection design.",
    "mysql": "JDBC reads should be handled through Dataflow, Dataproc or a reviewed BigQuery external connection design.",
    "native_passthrough": "Native connector handoff needs a specific Google Cloud service design before BigQuery runtime support.",
    "oracle": "JDBC reads should be handled through Dataflow, Dataproc or a reviewed BigQuery external connection design.",
    "redshift": "JDBC reads should be handled through Dataflow, Dataproc or a reviewed BigQuery external connection design.",
    "sqlserver": "JDBC reads should be handled through Dataflow, Dataproc or a reviewed BigQuery external connection design.",
    "snowflake_jdbc": "JDBC reads should be handled through Dataflow, Dataproc or a reviewed BigQuery external connection design.",
    "kafka_bounded": "Kafka replay needs Pub/Sub, Dataflow or a bounded staging design before BigQuery support.",
    "kafka_available_now": "Available-now streaming needs Pub/Sub/Dataflow checkpoint semantics before BigQuery support.",
    "eventhubs_bounded": "Event Hubs replay needs a cross-cloud staging design before BigQuery support.",
    "eventhubs_available_now": "Event Hubs streaming needs a cross-cloud staging design before BigQuery support.",
}


@dataclass(frozen=True)
class GCPSourceClassification:
    source_type: str
    status: str
    native_mapping: str | None
    note: str
    renderable: bool


def classify_gcp_source(source: dict[str, Any] | str | None) -> GCPSourceClassification:
    payload = {"type": source} if isinstance(source, str) else dict(source or {})
    source_type = str(payload.get("connector") or payload.get("type") or "").strip().lower()
    if is_rest_api_connector(payload):
        return _rest_api_classification(payload, source_type)
    if is_http_file_source(payload):
        return _http_file_classification(payload, source_type)
    if source_type in _CATALOG_SOURCES:
        return GCPSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="BigQuery table, view or SQL query",
            note="BigQuery SQL can read the declared catalog/query source directly.",
            renderable=True,
        )
    if source_type in _BIGQUERY_LOAD_FORMATS:
        return _file_classification(payload, source_type)
    if source_type in _OBJECT_STORAGE_SOURCES:
        return _object_storage_classification(payload, source_type)
    if source_type == "iceberg_table":
        return _iceberg_table_classification(payload)
    if source_type in _REVIEW_SOURCES:
        return GCPSourceClassification(
            source_type=source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Google Cloud staging/runtime design required",
            note=_REVIEW_SOURCES[source_type],
            renderable=False,
        )
    return GCPSourceClassification(
        source_type=source_type,
        status=UNSUPPORTED,
        native_mapping=None,
        note="No GCP BigQuery source mapping is declared for this connector.",
        renderable=False,
    )


def gcp_source_support(source: dict[str, Any] | str | None) -> dict[str, Any]:
    classification = classify_gcp_source(source)
    entry: dict[str, Any] = {
        "adapter": "gcp",
        "subtarget": "gcp_bigquery",
        "source_type": classification.source_type,
        "status": classification.status,
        "note": classification.note,
        "renderable": classification.renderable,
    }
    if classification.native_mapping:
        entry["native_mapping"] = classification.native_mapping
    return entry


def is_gcp_source_renderable(source: dict[str, Any] | str | None) -> bool:
    return classify_gcp_source(source).renderable


def list_gcp_source_support() -> tuple[dict[str, Any], ...]:
    sources = tuple(name for name in CONNECTOR_CATALOG if name != "connection")
    return tuple(gcp_source_support(source) for source in sources)


def review_required_gcp_source_types() -> tuple[str, ...]:
    """Return source families that should be published as review-required capabilities."""

    return tuple(sorted((*_REVIEW_SOURCES, "http_file", "iceberg_table")))


def _file_classification(source: dict[str, Any], source_type: str) -> GCPSourceClassification:
    path = str(source.get("path") or "").strip()
    if path.startswith("gs://"):
        return GCPSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="BigQuery load job from Google Cloud Storage",
            note="Renderable as a BigQuery load job configuration using the declared GCS URI.",
            renderable=True,
        )
    return GCPSourceClassification(
        source_type=source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Google Cloud Storage staging before BigQuery load",
        note="BigQuery load rendering requires a gs:// path or an upstream contract that lands the file in GCS.",
        renderable=False,
    )


def _object_storage_classification(source: dict[str, Any], source_type: str) -> GCPSourceClassification:
    provider = str(source.get("provider") or "").strip().lower()
    path = str(source.get("path") or "").strip()
    fmt = str(source.get("format") or source.get("file_format") or "").strip().lower()
    if (source_type == "gcs" or provider == "gcp") and path.startswith("gs://") and fmt in _BIGQUERY_LOAD_FORMATS:
        return GCPSourceClassification(
            source_type=source_type,
            status=SUPPORTED,
            native_mapping="BigQuery load job from Google Cloud Storage",
            note="Renderable as a BigQuery load job configuration using the declared GCS URI.",
            renderable=True,
        )
    return GCPSourceClassification(
        source_type=source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Google Cloud Storage staging before BigQuery load",
        note="Object storage reads need provider=gcp, a supported format and a gs:// path for the v1 BigQuery renderer.",
        renderable=False,
    )


def _iceberg_table_classification(source: dict[str, Any]) -> GCPSourceClassification:
    table = str(source.get("table") or source.get("table_ref") or source.get("ref") or "").strip()
    path = str(source.get("path") or "").strip()
    if table:
        return GCPSourceClassification(
            source_type="iceberg_table",
            status=SUPPORTED,
            native_mapping="Registered BigQuery BigLake managed Iceberg table",
            note="Renderable when the Iceberg table is already registered as a BigQuery table.",
            renderable=True,
        )
    if path.startswith("gs://"):
        return GCPSourceClassification(
            source_type="iceberg_table",
            status=REVIEW_REQUIRED,
            native_mapping="BigLake Iceberg table registration required",
            note="Raw Iceberg storage paths need BigQuery connection, bucket IAM and table registration before query rendering.",
            renderable=False,
        )
    return GCPSourceClassification(
        source_type="iceberg_table",
        status=REVIEW_REQUIRED,
        native_mapping="BigLake/Iceberg table binding required",
        note="Declare a registered BigQuery table reference or register the Iceberg table before runtime support.",
        renderable=False,
    )


def _rest_api_classification(source: dict[str, Any], source_type: str) -> GCPSourceClassification:
    if _has_auth(source):
        if has_secret_placeholders(source.get("auth")):
            return GCPSourceClassification(
                source_type=source_type,
                status=SUPPORTED_WITH_WARNINGS,
                native_mapping="Core REST client plus Secret Manager auth resolution and BigQuery local load",
                note="Authenticated REST reads execute through shared core readers when credentials use {{ secret:scope/key }} placeholders resolved from Secret Manager at runtime.",
                renderable=True,
            )
        return GCPSourceClassification(
            source_type=source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Core REST client plus BigQuery local load with reviewed secret resolution",
            note="Authenticated REST reads need Secret Manager or environment-bound credential resolution before runtime support.",
            renderable=False,
        )
    return GCPSourceClassification(
        source_type=source_type,
        status=SUPPORTED_WITH_WARNINGS,
        native_mapping="Core REST client plus BigQuery local NDJSON load",
        note="Public/no-auth bounded REST reads materialize through the shared core REST client, then load NDJSON into BigQuery.",
        renderable=True,
    )


def _http_file_classification(source: dict[str, Any], source_type: str) -> GCPSourceClassification:
    fmt = _http_source_format(source)
    if source_type == "http_text" or (source_type == "http_file" and fmt == "text"):
        if _has_auth(source) and not has_secret_placeholders(source.get("auth")):
            return GCPSourceClassification(
                source_type=source_type,
                status=REVIEW_REQUIRED,
                native_mapping="Core HTTP fetch plus BigQuery local load with reviewed secret resolution",
                note="Authenticated HTTP text reads need Secret Manager or environment-bound credential resolution before runtime support.",
                renderable=False,
            )
        return GCPSourceClassification(
            source_type=source_type,
            status=SUPPORTED_WITH_WARNINGS,
            native_mapping="Core HTTP fetch plus BigQuery local line-oriented NDJSON load",
            note="Bounded HTTP text reads materialize each text line into a declared string column, then load NDJSON into BigQuery.",
            renderable=True,
        )
    if source_type == "http_file":
        if fmt not in {"avro", "csv", "json", "jsonl", "ndjson", "orc", "parquet"}:
            return GCPSourceClassification(
                source_type=source_type,
                status=REVIEW_REQUIRED,
                native_mapping="Core HTTP fetch plus reviewed BigQuery load",
                note="Generic HTTP file sources need source.format or response.format set to avro, csv, json, jsonl, ndjson, orc, parquet or text before GCP runtime support.",
                renderable=False,
            )
        if _has_auth(source) and not has_secret_placeholders(source.get("auth")):
            return GCPSourceClassification(
                source_type=source_type,
                status=REVIEW_REQUIRED,
                native_mapping="Core HTTP fetch plus BigQuery local load with reviewed secret resolution",
                note="Authenticated HTTP file reads need Secret Manager or environment-bound credential resolution before runtime support.",
                renderable=False,
            )
        fmt_label = {
            "avro": "AVRO",
            "csv": "CSV",
            "json": "NDJSON",
            "jsonl": "NDJSON",
            "ndjson": "NDJSON",
            "orc": "ORC",
            "parquet": "PARQUET",
        }[fmt]
        return GCPSourceClassification(
            source_type=source_type,
            status=SUPPORTED_WITH_WARNINGS,
            native_mapping=f"Core HTTP fetch plus BigQuery local {fmt_label} load",
            note="Generic bounded HTTP file reads materialize through the shared core HTTP reader when the contract declares a supported tabular format.",
            renderable=True,
        )
    if _has_auth(source):
        if has_secret_placeholders(source.get("auth")):
            return GCPSourceClassification(
                source_type=source_type,
                status=SUPPORTED_WITH_WARNINGS,
                native_mapping="Core HTTP fetch plus Secret Manager auth resolution and BigQuery local load",
                note="Authenticated HTTP file reads execute through shared core readers when credentials use {{ secret:scope/key }} placeholders resolved from Secret Manager at runtime.",
                renderable=True,
            )
        return GCPSourceClassification(
            source_type=source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Core HTTP fetch plus BigQuery local load with reviewed secret resolution",
            note="Authenticated HTTP file reads need Secret Manager or environment-bound credential resolution before runtime support.",
            renderable=False,
        )
    if source_type in {"http_json", "http_csv"}:
        fmt = "NDJSON" if source_type == "http_json" else "CSV"
        return GCPSourceClassification(
            source_type=source_type,
            status=SUPPORTED_WITH_WARNINGS,
            native_mapping=f"Core HTTP fetch plus BigQuery local {fmt} load",
            note="Public/no-auth bounded HTTP file reads materialize through the shared core HTTP reader, then load into BigQuery.",
            renderable=True,
        )
    return GCPSourceClassification(
        source_type=source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Core HTTP fetch plus reviewed BigQuery load",
        note="HTTP file sources need a declared avro/csv/json/orc/parquet/text subtype or a staged GCS landing contract before runtime support.",
        renderable=False,
    )


def _has_auth(source: dict[str, Any]) -> bool:
    auth = source.get("auth")
    if not isinstance(auth, dict):
        return False
    auth_type = str(auth.get("type") or "").strip().lower()
    return auth_type not in {"", "none"}


def _http_source_format(source: dict[str, Any]) -> str:
    try:
        return str(http_file_format(source)).strip().lower()
    except Exception:
        response = source.get("response") if isinstance(source.get("response"), dict) else {}
        return str(source.get("format") or response.get("format") or "").strip().lower()
