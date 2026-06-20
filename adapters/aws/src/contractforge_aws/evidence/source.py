"""Map AWS source metadata into canonical run-evidence fields."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import source_metadata_from_contract
from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_aws.sources import aws_source_support


def source_run_evidence_fields(contract: SemanticContract, *, target_table: str) -> dict[str, Any]:
    source = contract.source.raw or {}
    metadata = source_metadata_from_contract(contract, target_table=target_table)
    metadata["source_capabilities"] = aws_source_support(source)
    return {
        "source_type": metadata.get("source_type"),
        "source_connector": metadata.get("source_connector") or source.get("type"),
        "source_name": metadata.get("source_name"),
        "source_system": metadata.get("source_system"),
        "source_provider": metadata.get("source_provider"),
        "source_format": metadata.get("source_format") or _format_from_type(source),
        "source_path": metadata.get("source_path"),
        "source_options_json": metadata.get("source_options"),
        "source_read_json": metadata.get("source_read") or redact_value(source),
        "source_request_json": metadata.get("source_request"),
        "source_auth_json": metadata.get("source_auth"),
        "source_pagination_json": metadata.get("source_pagination"),
        "source_response_json": metadata.get("source_response"),
        "source_incremental_json": metadata.get("source_incremental"),
        "source_limits_json": metadata.get("source_limits"),
        "source_capabilities_json": metadata.get("source_capabilities"),
    }


def _format_from_type(source: dict[str, Any]) -> str | None:
    source_type = source.get("type")
    if source_type in {"csv", "json", "jsonl", "ndjson", "parquet", "orc", "avro", "xml", "text"}:
        return str(source_type)
    return None
