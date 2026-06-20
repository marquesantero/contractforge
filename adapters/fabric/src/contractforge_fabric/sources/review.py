"""Contract-specific Fabric source review artifacts."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.connectors import (
    JDBC_CONNECTORS,
    OBJECT_STORAGE_TYPES,
    is_available_now_stream_source,
    is_bounded_stream_source,
    is_delta_share_source,
    is_http_file_source,
    is_native_passthrough_source,
    is_rest_api_connector,
)
from contractforge_core.security import redact_value
from contractforge_fabric.sources.classification import classify_fabric_source
from contractforge_fabric.sources.object_storage import fabric_object_storage_runtime_path


def fabric_source_review_payload(source: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted, contract-specific Fabric source review payload."""

    classification = classify_fabric_source(source)
    source_type = classification.source_type
    return {
        "adapter": "fabric",
        "source_type": source_type,
        "status": classification.status,
        "renderable": classification.renderable,
        "native_mapping": classification.native_mapping,
        "note": classification.note,
        "source_redacted": redact_value(source),
        "runtime_path": _runtime_path(source),
        "review_prerequisites": _review_prerequisites(source),
        "graduation_gates": _graduation_gates(source),
    }


def render_fabric_source_review_json(source: dict[str, Any]) -> str:
    return json.dumps(fabric_source_review_payload(source), indent=2, sort_keys=True)


def render_fabric_source_review_markdown(source: dict[str, Any]) -> str:
    payload = fabric_source_review_payload(source)
    lines = [
        "# Fabric Source Review",
        "",
        f"- Source type: `{payload['source_type']}`",
        f"- Status: `{payload['status']}`",
        f"- Renderable notebook source: `{payload['renderable']}`",
        f"- Native mapping: `{payload['native_mapping'] or 'UNSPECIFIED'}`",
        f"- Runtime path: `{payload['runtime_path']}`",
        "",
        "## Review Prerequisites",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["review_prerequisites"])
    lines.extend(["", "## Graduation Gates", ""])
    lines.extend(f"- {item}" for item in payload["graduation_gates"])
    lines.extend(["", "## Redacted Source", "", "```json", json.dumps(payload["source_redacted"], indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def _runtime_path(source: dict[str, Any]) -> str:
    source_type = str(source.get("connector") or source.get("type") or "").strip().lower()
    if source_type in OBJECT_STORAGE_TYPES:
        runtime_path = fabric_object_storage_runtime_path(source)
        if runtime_path:
            return f"Fabric notebook read from `{runtime_path}`"
        return "OneLake shortcut or staged copy into Lakehouse Files"
    if source_type == "incremental_files":
        return "Fabric Data Factory incremental pipeline or notebook checkpoint"
    if _is_jdbc(source):
        return "Fabric Data Factory connection or reviewed notebook JDBC read"
    if is_available_now_stream_source(source) or is_bounded_stream_source(source):
        return "Fabric Real-Time Intelligence/Eventstream or reviewed bounded replay"
    if is_delta_share_source(source):
        return "Delta Sharing client materialized into OneLake"
    if is_rest_api_connector(source):
        return "Fabric notebook bounded REST fetch or Data Factory REST copy"
    if is_http_file_source(source):
        return "Fabric notebook bounded HTTP fetch or Data Factory web activity"
    if is_native_passthrough_source(source):
        return "Fabric native connector, shortcut or Data Factory activity"
    return "Fabric Lakehouse notebook source read"


def _review_prerequisites(source: dict[str, Any]) -> list[str]:
    source_type = str(source.get("connector") or source.get("type") or "").strip().lower()
    if source_type in OBJECT_STORAGE_TYPES:
        return [
            "Create or identify the OneLake shortcut or staged Lakehouse Files location.",
            "Validate credential ownership, tenant boundary, network path and data residency.",
            "Prove compatible Delta/Parquet/table recognition behavior when using shortcuts.",
        ]
    if source_type == "incremental_files":
        return [
            "Choose one checkpoint owner: Fabric Data Factory state, ContractForge state table or a notebook checkpoint path.",
            "Define replay behavior for late files, duplicate files and partial failures.",
            "Record discovered-file evidence before the target write.",
        ]
    if _is_jdbc(source):
        return [
            "Define Fabric connection or gateway ownership and secret placement outside the contract body.",
            "Validate driver availability, private-network access and source-side read isolation.",
            "Document predicate pushdown, partitioning and bounded extraction limits.",
        ]
    if is_available_now_stream_source(source) or is_bounded_stream_source(source):
        return [
            "Choose Eventstream/Real-Time Intelligence or notebook bounded replay as the runtime path.",
            "Define starting offsets, ending offsets, checkpoint storage and replay idempotency.",
            "Validate evidence for consumed offsets and bounded-run completion.",
        ]
    if is_delta_share_source(source):
        return [
            "Resolve the Delta Sharing profile through a Fabric-compatible secret location.",
            "Pin runtime dependencies and materialize the shared table into OneLake before downstream writes.",
            "Validate versioned reads, schema drift behavior and provider revocation handling.",
        ]
    if is_rest_api_connector(source) or is_http_file_source(source):
        return [
            "Keep public/no-auth bounded sources notebook-renderable, or design a Fabric secret resolver for authenticated sources.",
            "Validate timeout, retry, rate-limit and payload-size behavior in Fabric Spark.",
            "Record request metadata without exposing credentials or sensitive headers.",
        ]
    if is_native_passthrough_source(source):
        return [
            "Name the native Fabric connector or pipeline activity that owns extraction.",
            "Document where landed data appears in OneLake before ContractForge processing starts.",
            "Attach connector-specific credentials, network and retry behavior for review.",
        ]
    return ["Validate the Fabric runtime reader, credentials and evidence behavior for this source type."]


def _graduation_gates(source: dict[str, Any]) -> list[str]:
    return [
        "Generated artifacts are derived only from contracts and Fabric environment bindings.",
        "Bronze-to-gold execution succeeds in Fabric without notebook or pipeline workaround code.",
        "Run, source metadata, schema, quality, lineage and error evidence are written for success and failure paths.",
        f"`{classify_fabric_source(source).source_type}` is covered by a real Fabric smoke or parity test fixture.",
    ]


def _is_jdbc(source: dict[str, Any]) -> bool:
    connector = source.get("connector") or source.get("type")
    return connector in JDBC_CONNECTORS or source.get("type") == "jdbc"


__all__ = [
    "fabric_source_review_payload",
    "render_fabric_source_review_json",
    "render_fabric_source_review_markdown",
]
