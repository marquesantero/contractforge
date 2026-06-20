"""Platform-neutral source metadata helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors.registry import CONNECTOR_CATALOG, connector_catalog_entry
from contractforge_core.contracts.source_portability import classify_source_type
from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract


def source_capabilities(source_type: str) -> dict[str, bool]:
    classification = classify_source_type(source_type)
    return {
        "bounded": source_type not in {"incremental_files"},
        "incremental": bool(connector_catalog_entry(source_type).get("incremental")),
        "native_passthrough": classification.portability == "NATIVE_PASSTHROUGH",
    }


def source_connector_details(name: str) -> dict[str, Any]:
    normalized = str(name or "").strip().lower()
    classification = classify_source_type(normalized)
    builtin = connector_catalog_entry(normalized)
    details: dict[str, Any] = {
        "name": normalized,
        "builtin": bool(builtin),
        "family": builtin.get("family", "custom" if classification.portability == "UNSUPPORTED" else "portable"),
        "description": builtin.get("description"),
        "required": list(builtin.get("required") or []),
        "required_any_of": list(builtin.get("required_any_of") or []),
        "conditional_required": list(builtin.get("conditional_required") or []),
        "runtime": builtin.get("runtime"),
        "auth_modes": list(builtin.get("auth_modes") or []),
        "supported_formats": list(builtin.get("supported_formats") or []),
        "providers": list(builtin.get("providers") or []),
        "limits": list(builtin.get("limits") or []),
        "recommended_usage": builtin.get("recommended_usage"),
        "runtime_notes": list(builtin.get("runtime_notes") or []),
        "incremental": bool(builtin.get("incremental")),
        "portability": classification.portability,
        "adapter": classification.adapter,
        "reason": classification.reason,
        "capabilities": source_capabilities(normalized),
    }
    return {key: value for key, value in details.items() if value not in (None, [], {})}


def list_source_connector_details() -> list[dict[str, Any]]:
    return [source_connector_details(name) for name in sorted(CONNECTOR_CATALOG)]


def diagnose_source_connectors(names: list[str] | tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    connector_names = list(names) if names else sorted(CONNECTOR_CATALOG)
    diagnostics = []
    for name in connector_names:
        item = source_connector_details(name)
        portability = item["portability"]
        if portability == "UNSUPPORTED":
            status = "FAILED"
            recommendation = "Use a portable source type or native_passthrough."
        elif portability == "NATIVE_PASSTHROUGH":
            status = "WARNED"
            recommendation = "Adapter will render native review artifacts; behavior is platform-owned."
        else:
            status = "SUCCESS"
            recommendation = "Supported by the core source taxonomy."
        diagnostics.append({**item, "status": status, "recommendation": recommendation})
    return diagnostics


def source_provider(source_type: str, connector: object = None, source: dict[str, Any] | None = None) -> str | None:
    payload = source or {}
    raw = str(connector or source_type).lower()
    path = str(payload.get("path") or payload.get("url") or "").lower()
    if path.startswith("s3://"):
        return "aws"
    if path.startswith(("abfss://", "wasbs://", "azure://")):
        return "azure"
    if path.startswith("gs://"):
        return "gcp"
    if raw in {"s3", "redshift"}:
        return "aws"
    if raw in {"adls", "azure_blob", "eventhubs_bounded", "eventhubs_available_now", "sqlserver"}:
        return "azure"
    if raw in {"gcs", "bigquery_jdbc"}:
        return "gcp"
    if raw in {"snowflake_jdbc"}:
        return "snowflake"
    return None


def source_metadata_from_contract(contract: SemanticContract, *, target_table: str | None = None) -> dict[str, Any]:
    source = dict(contract.source.raw or {})
    return source_metadata_from_mapping(
        source,
        source_kind=contract.source.kind,
        source_name=contract.source.name,
        target_table=target_table or contract.target.name,
    )


def source_metadata_from_mapping(
    source: dict[str, Any],
    *,
    source_kind: str | None = None,
    source_name: str | None = None,
    target_table: str | None = None,
) -> dict[str, Any]:
    source_type = str(source.get("type") or source_kind or "source")
    connector = source.get("connector")
    capability_type = str(connector or source_type)
    capabilities = source_capabilities(capability_type)
    capabilities["source_complete"] = _source_complete(source_type, source)
    metadata = {
        "target_table": target_table,
        "source_type": source_type,
        "source_intent": source.get("intent"),
        "source_kind": source_kind,
        "source_name": source_name or source.get("name"),
        "source_connector": connector,
        "source_system": source.get("system"),
        "source_provider": source.get("provider") or source_provider(source_type, connector, source),
        "source_mode": source.get("mode"),
        "source_connection": source.get("connection"),
        "source_format": source.get("format"),
        "source_path": source.get("path") or source.get("url") or source.get("table"),
        "source_host": source.get("host"),
        "source_port": source.get("port"),
        "source_mailbox": source.get("mailbox"),
        "source_object": source.get("object"),
        "source_url": source.get("url"),
        "source_environment_url": source.get("environment_url"),
        "source_entity": source.get("entity"),
        "source_index": source.get("index"),
        "source_table": source.get("table"),
        "source_query": bool(source.get("query") or _dict(source.get("options")).get("query")),
        "source_options": _dict(source.get("options")),
        "source_read": _subset(source, ("table", "query", "path", "format", "delimiter", "header")),
        "source_request": _dict(source.get("request")),
        "source_auth": _dict(source.get("auth")),
        "source_pagination": _dict(source.get("pagination")),
        "source_response": _dict(source.get("response")),
        "source_incremental": _incremental(source),
        "source_discovery": _dict(source.get("discovery")),
        "source_state": _dict(source.get("state")),
        "source_limits": _limits(source),
        "source_capabilities": capabilities,
    }
    return {key: value for key, value in redact_value(metadata).items() if value not in (None, {}, [])}


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _subset(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: source[key] for key in keys if key in source}


def _incremental(source: dict[str, Any]) -> dict[str, Any]:
    incremental = _dict(source.get("incremental"))
    keys = (
        "watermark",
        "watermark_column",
        "progress_location",
        "schema_tracking_location",
        "checkpoint_location",
        "trigger",
        "max_files_per_trigger",
    )
    incremental.update({key: source[key] for key in keys if key in source})
    return incremental


def _limits(source: dict[str, Any]) -> dict[str, Any]:
    limits = _dict(source.get("limits"))
    limits.update(
        {
            key: source[key]
            for key in (
                "timeout_seconds",
                "max_bytes",
                "max_records",
                "max_offsets_per_trigger",
                "max_events_per_trigger",
            )
            if key in source
        }
    )
    return limits


def _source_complete(source_type: str, source: dict[str, Any]) -> bool:
    read = _dict(source.get("read"))
    if read.get("source_complete") is not None:
        return _bool_value(read.get("source_complete"))
    if read.get("full_snapshot") is not None:
        return _bool_value(read.get("full_snapshot"))
    if source.get("source_complete") is not None:
        return _bool_value(source.get("source_complete"))
    if source_type in {"table", "delta_table", "iceberg_table", "view"}:
        return True
    return False


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "sim"}:
        return True
    if text in {"0", "false", "no", "n", "nao", "não"}:
        return False
    return bool(value)
