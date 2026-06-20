"""Contract-specific GCP source review artifacts."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.security import redact_value
from contractforge_gcp.sources import REVIEW_REQUIRED, SUPPORTED, SUPPORTED_WITH_WARNINGS, classify_gcp_source


def gcp_source_review_payload(source: dict[str, Any] | str | None) -> dict[str, Any]:
    """Return a redacted, contract-specific GCP source review payload."""

    classification = classify_gcp_source(source)
    return {
        "adapter": "gcp",
        "subtarget": "gcp_bigquery",
        "source_type": classification.source_type,
        "status": classification.status,
        "renderable": classification.renderable,
        "native_mapping": classification.native_mapping,
        "note": classification.note,
        "source_redacted": redact_value(source),
        "runtime_path": _runtime_path(source),
        "review_prerequisites": _review_prerequisites(source),
        "graduation_gates": _graduation_gates(source),
        "promotion_path": _promotion_path(source),
    }


def render_gcp_source_review_json(source: dict[str, Any] | str | None) -> str:
    return json.dumps(gcp_source_review_payload(source), indent=2, sort_keys=True)


def render_gcp_source_review_markdown(source: dict[str, Any] | str | None) -> str:
    payload = gcp_source_review_payload(source)
    lines = [
        "# GCP Source Review",
        "",
        f"- Source type: `{payload['source_type']}`",
        f"- Status: `{payload['status']}`",
        f"- Renderable BigQuery source: `{payload['renderable']}`",
        f"- Native mapping: `{payload['native_mapping'] or 'UNSPECIFIED'}`",
        f"- Runtime path: `{payload['runtime_path']}`",
        "",
        "## Review Prerequisites",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["review_prerequisites"])
    lines.extend(["", "## Graduation Gates", ""])
    lines.extend(f"- {item}" for item in payload["graduation_gates"])
    promotion_path = payload["promotion_path"]
    if promotion_path:
        lines.extend(["", "## Promotion Path", ""])
        lines.extend(
            [
                f"- Candidate runtime: {promotion_path['candidate_runtime']}",
                f"- Stable claim: {promotion_path['stable_claim']}",
                "",
                "### Required Bindings",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in promotion_path["required_bindings"])
        lines.extend(["", "### Evidence Required", ""])
        lines.extend(f"- {item}" for item in promotion_path["evidence_required"])
        lines.extend(["", "### Blockers", ""])
        lines.extend(f"- {item}" for item in promotion_path["blockers"])
    lines.extend(["", "## Redacted Source", "", "```json", json.dumps(payload["source_redacted"], indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def _runtime_path(source: dict[str, Any] | str | None) -> str:
    classification = classify_gcp_source(source)
    source_type = classification.source_type
    if source_type in {"table", "view", "sql"}:
        return "BigQuery table, view or GoogleSQL query"
    if source_type in {"avro", "csv", "json", "jsonl", "ndjson", "orc", "parquet", "gcs", "blob", "object_storage"}:
        return "BigQuery load job from Cloud Storage when the contract resolves to gs:// input"
    if source_type == "iceberg_table":
        return "Registered BigQuery/BigLake Iceberg table, or reviewed table registration for raw paths"
    if source_type in {"rest_api", "api", "http_api", "http_csv", "http_json", "http_text", "http_file"}:
        if classification.renderable:
            return "Shared core bounded reader, temporary local materialization and BigQuery load job"
        return "Reviewed credential resolution before shared core reader and BigQuery load job"
    if source_type in {"http_file", "http_text"}:
        return "Reviewed parsing or staged GCS landing before BigQuery processing"
    if source_type in {"kafka_bounded", "kafka_available_now", "eventhubs_bounded", "eventhubs_available_now"}:
        return "Dataflow or Pub/Sub staging with explicit offset and checkpoint evidence"
    if source_type in {"delta", "delta_table", "delta_share"}:
        return "BigLake/external table handoff, Dataproc/Spark materialization or staged copy"
    if "jdbc" in source_type or source_type in {"db2", "mariadb", "mysql", "oracle", "postgres", "redshift", "sqlserver"}:
        return "Reviewed BigQuery external connection, Dataflow or Dataproc extraction"
    return "Reviewed Google Cloud landing/runtime design"


def _review_prerequisites(source: dict[str, Any] | str | None) -> list[str]:
    classification = classify_gcp_source(source)
    if classification.status in {SUPPORTED, SUPPORTED_WITH_WARNINGS}:
        return [
            "Validate target project, dataset, service-account IAM and BigQuery job permissions.",
            "Record run, schema, quality and source metadata evidence in BigQuery audit tables.",
            "Keep the contract as the only source of adapter behavior; environment files may only bind runtime locations.",
        ]
    if classification.status == REVIEW_REQUIRED:
        return [
            classification.note,
            "Choose and document the Google Cloud runtime owner before claiming execution support.",
            "Validate credentials, network path, retry behavior, schema drift and evidence readback in a real GCP smoke.",
        ]
    return [
        classification.note,
        "Add an adapter-owned classifier entry before rendering or executing this source type.",
        "Promote only after the generated contract path has real-account evidence without workaround code.",
    ]


def _graduation_gates(source: dict[str, Any] | str | None) -> list[str]:
    source_type = classify_gcp_source(source).source_type
    return [
        "Generated artifacts are derived only from contracts and GCP environment bindings.",
        "Bronze-to-gold execution succeeds in GCP without one-off notebooks, scripts or manual staging.",
        "Run, source metadata, schema, quality, lineage and error evidence are written for success and failure paths.",
        f"`{source_type}` is covered by a real GCP smoke or cross-adapter parity fixture.",
    ]


def _promotion_path(source: dict[str, Any] | str | None) -> dict[str, Any]:
    payload = {"type": source} if isinstance(source, str) else dict(source or {})
    classification = classify_gcp_source(payload)
    source_type = classification.source_type
    if source_type == "iceberg_table":
        table = str(payload.get("table") or payload.get("table_ref") or payload.get("ref") or "").strip()
        path = str(payload.get("path") or "").strip()
        if table:
            return {}
        return {
            "candidate_runtime": "Register the raw Iceberg location as a BigQuery/BigLake table before query rendering.",
            "stable_claim": "Review-required until registration, IAM and query/evidence readback pass in GCP.",
            "required_bindings": [
                "BigQuery connection in the same compatible location as the dataset.",
                "Cloud Storage IAM for the BigQuery connection service account on the Iceberg metadata and data prefix.",
                f"Raw Iceberg path declared in the contract: {path or 'UNSPECIFIED'}.",
            ],
            "evidence_required": [
                "Generated BigLake registration plan records bq mk flags, connection/IAM bindings and post-registration source shape.",
                "Registered table metadata readback proves the target table points to the declared Iceberg location.",
                "BigQuery query readback validates row counts and schema from the registered table.",
                "Run, source metadata, schema, quality and lineage evidence use the same ContractForge run id.",
            ],
            "blockers": [
                "No stable direct raw-path query is claimed; the stable path is registered table access.",
                "Registration cannot be inferred from a gs:// path without connection and IAM evidence.",
            ],
        }
    if source_type in {"delta", "delta_table", "delta_share"}:
        return {
            "candidate_runtime": "Materialize Delta or Delta Sharing data through Dataproc/Spark or a governed staged copy.",
            "stable_claim": "Review-required until GCP proves versioned read, schema drift and evidence semantics.",
            "required_bindings": [
                "Secret or profile binding outside the contract body for Delta Sharing credentials.",
                "Pinned runtime dependency set for Delta/Delta Sharing client reads.",
                "Declared landing target, preferably GCS or BigQuery, before downstream ContractForge writes.",
            ],
            "evidence_required": [
                "Generated Delta materialization plan records Dataproc runtime, dependency set, landing prefix and post-materialization table source.",
                "Versioned read or snapshot identifier captured without exposing provider credentials.",
                "Source row count, target row count and schema evidence captured for the same run id.",
                "Provider revocation, missing table and schema drift failure paths persist failed-run evidence.",
            ],
            "blockers": [
                "BigQuery does not become stable merely because a staged copy exists.",
                "Manual export/import or notebook-only materialization is not acceptable promotion evidence.",
            ],
        }
    if source_type in {"kafka_bounded", "kafka_available_now", "eventhubs_bounded", "eventhubs_available_now"}:
        return {
            "candidate_runtime": "Dataflow or Pub/Sub staging with explicit offset/checkpoint ownership.",
            "stable_claim": "Review-required until bounded replay or available-now catch-up semantics match other adapters.",
            "required_bindings": [
                "Network and credential boundary for the streaming provider.",
                "Checkpoint or offset store owned by the generated GCP runtime.",
                "Target landing table or GCS staging prefix before BigQuery writes.",
            ],
            "evidence_required": [
                "Generated Dataflow streaming plan records template parameters, checkpoint location, consumer group and offset readback requirements.",
                "Starting offsets, ending offsets and consumed offsets are recorded for each run.",
                "Rerun/idempotency behavior is validated for bounded and available-now paths.",
                "Run, quality, source metadata and lineage evidence are persisted for success and failure paths.",
            ],
            "blockers": [
                "Direct Pub/Sub-to-BigQuery subscriptions do not prove Kafka available-now semantics.",
                "Unbounded streaming is outside the current batch stable surface.",
            ],
        }
    if "jdbc" in source_type or source_type in {"db2", "mariadb", "mysql", "oracle", "postgres", "redshift", "sqlserver"}:
        return {
            "candidate_runtime": "Dataflow JDBC to BigQuery batch template with adapter-owned readback.",
            "stable_claim": "Review-required until bronze-to-gold execution, schema drift and evidence semantics pass in GCP.",
            "required_bindings": [
                "JDBC driver JAR staged in Google Cloud Storage or Secret Manager.",
                "Connection URL and credentials resolved from Secret Manager or reviewed environment bindings.",
                "BigQuery target table or schema-file binding before the Dataflow load starts.",
                "Network path from Dataflow workers to the database endpoint.",
            ],
            "evidence_required": [
                "Generated Dataflow JDBC plan records driver, query/table, target table and temp directory.",
                "Dataflow job id, final state and BigQuery output row count are read back.",
                "Downstream bronze-to-gold contracts read the promoted BigQuery table without connector-specific rewrites.",
                "Credential, network and schema failures persist failed-run evidence without leaking secrets.",
            ],
            "blockers": [
                "A local JDBC read or manual export/import is not GCP adapter promotion evidence.",
                "The database must be reachable from the Dataflow worker subnet or the job is expected to fail.",
            ],
        }
    if source_type == "http_file" and not classification.renderable:
        return {
            "candidate_runtime": "Explicit parser plus staged GCS or temporary local materialization before BigQuery load.",
            "stable_claim": "Review-required until the contract declares table parsing rules and failure evidence.",
            "required_bindings": [
                "Parser settings that convert text payloads into a declared tabular schema.",
                "Bounded payload limits, retry policy and timeout policy.",
                "Credential resolver when the HTTP source is authenticated.",
            ],
            "evidence_required": [
                "Malformed payloads produce failed-run evidence without partial target writes.",
                "Parsed row counts and quality evidence match the declared schema.",
                "Request metadata is recorded without leaking headers or credentials.",
            ],
            "blockers": [
                "Free-form text cannot be treated as a BigQuery table without declared parsing semantics.",
                "Authenticated text reads also need Secret Manager or equivalent credential evidence.",
            ],
        }
    return {}


__all__ = [
    "gcp_source_review_payload",
    "render_gcp_source_review_json",
    "render_gcp_source_review_markdown",
]
