"""Fabric source connector classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from contractforge_core.connectors import (
    FILE_SOURCE_TYPES,
    JDBC_CONNECTORS,
    OBJECT_STORAGE_TYPES,
    is_available_now_stream_source,
    is_bounded_stream_source,
    is_catalog_source,
    is_delta_share_source,
    is_http_file_source,
    is_native_passthrough_source,
    is_rest_api_connector,
)
from contractforge_fabric.security import contains_secret_placeholder
from contractforge_fabric.sources.object_storage import is_fabric_object_storage_renderable

SUPPORTED = "SUPPORTED"
SUPPORTED_WITH_WARNINGS = "SUPPORTED_WITH_WARNINGS"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
UNSUPPORTED = "UNSUPPORTED"

_V1_CATALOG_SOURCE_TYPES = frozenset({"table", "delta_table", "view", "sql"})
_V1_FILE_SOURCE_TYPES = frozenset({"avro", "csv", "json", "jsonl", "ndjson", "orc", "parquet", "delta", "text", "xml"})


@dataclass(frozen=True)
class FabricSourceClassification:
    source_type: str
    status: str
    native_mapping: str | None
    note: str
    renderable: bool


@dataclass(frozen=True)
class _SourceRule:
    matches: Callable[[dict[str, Any]], bool]
    classify: Callable[[dict[str, Any], str], FabricSourceClassification]


def classify_fabric_source(source: dict[str, Any] | str) -> FabricSourceClassification:
    payload = {"type": source} if isinstance(source, str) else dict(source)
    source_type = str(payload.get("connector") or payload.get("type") or "").strip().lower()
    for rule in _CLASSIFICATION_RULES:
        if rule.matches(payload):
            return rule.classify(payload, source_type)
    return FabricSourceClassification(
        source_type=source_type,
        status=UNSUPPORTED,
        native_mapping=None,
        note="No Fabric source mapping is declared for this connector.",
        renderable=False,
    )


def is_fabric_source_renderable(source: dict[str, Any]) -> bool:
    return classify_fabric_source(source).renderable


def _is_jdbc_source(source: dict[str, Any]) -> bool:
    connector = source.get("connector") or source.get("type")
    return connector in JDBC_CONNECTORS or source.get("type") == "jdbc"


def _source_type(source: dict[str, Any]) -> str:
    return str(source.get("connector") or source.get("type") or "").strip().lower()


def _is_object_storage_source(source: dict[str, Any]) -> bool:
    return _source_type(source) in OBJECT_STORAGE_TYPES


def _supported(
    source_type: str,
    *,
    native_mapping: str,
    note: str,
    status: str = SUPPORTED,
    renderable: bool = True,
) -> FabricSourceClassification:
    return FabricSourceClassification(
        source_type=source_type,
        status=status,
        native_mapping=native_mapping,
        note=note,
        renderable=renderable,
    )


def _catalog_classification(_source: dict[str, Any], source_type: str) -> FabricSourceClassification:
    if source_type == "iceberg_table" and (_source.get("table") or _source.get("path") or _source.get("ref") or _source.get("table_ref")):
        return _supported(
            source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Fabric Lakehouse table shortcut virtualized from Iceberg",
            note="Iceberg table sources are notebook-renderable after Fabric creates a Tables shortcut to a valid Iceberg table folder; live evidence is still required for each shortcut provider.",
            renderable=True,
        )
    if source_type not in _V1_CATALOG_SOURCE_TYPES:
        return _supported(
            source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Fabric Lakehouse/Warehouse table or SQL endpoint",
            note="Catalog source is planning-compatible, but this table kind is outside the v1 runtime surface.",
            renderable=False,
        )
    return _supported(
        source_type,
        native_mapping="Fabric Lakehouse/Warehouse table or SQL endpoint",
        note="Notebook-first v1 candidate; logical refs are resolved to Fabric item/table names by the adapter.",
    )


def _file_classification(_source: dict[str, Any], source_type: str) -> FabricSourceClassification:
    if source_type in OBJECT_STORAGE_TYPES:
        if is_fabric_object_storage_renderable(_source):
            return _supported(
                source_type,
                status=REVIEW_REQUIRED,
                native_mapping="Fabric Lakehouse Files path, OneLake shortcut or Fabric-readable object-store URI",
                note="Object storage reads are notebook-renderable when the contract declares a Fabric-readable path or extensions.fabric.source_runtime_path points at a reviewed shortcut/staged Lakehouse location; live evidence is still required.",
                renderable=True,
            )
        return _supported(
            source_type,
            status=REVIEW_REQUIRED,
            native_mapping="OneLake shortcut or staged copy into Lakehouse Files",
            note="Object storage reads need shortcut, credential and security validation before v1 runtime support.",
            renderable=False,
        )
    if source_type not in _V1_FILE_SOURCE_TYPES:
        return _supported(
            source_type,
            status=REVIEW_REQUIRED,
            native_mapping="OneLake Files path read",
            note="File source is planning-compatible, but this format is outside the v1 runtime surface.",
            renderable=False,
        )
    return _supported(
        source_type,
        native_mapping="OneLake Files/Tables path read",
        note="Notebook-first v1 candidate for Lakehouse runtime artifacts.",
    )


def _jdbc_classification(_source: dict[str, Any], source_type: str) -> FabricSourceClassification:
    if _is_supported_jdbc_with_placeholder_auth(_source):
        family = _jdbc_family(_source)
        label = "PostgreSQL JDBC" if family == "postgres" else "SQL Server JDBC"
        return _supported(
            source_type,
            status=REVIEW_REQUIRED,
            native_mapping=f"Fabric notebook {label} read with Key Vault",
            note=f"{label} reads are notebook-renderable when Basic auth uses {{ secret:scope/key }} placeholders and the Fabric environment supplies Key Vault bindings; live evidence is still required.",
            renderable=True,
        )
    return _supported(
        source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Fabric Data Factory pipeline or notebook JDBC read",
        note="Driver, gateway, credential and private-network choices must be reviewed.",
        renderable=False,
    )


def _http_file_classification(_source: dict[str, Any], source_type: str) -> FabricSourceClassification:
    if _is_public_bounded_http(_source):
        return _supported(
            source_type,
            status=SUPPORTED_WITH_WARNINGS,
            native_mapping="Fabric notebook bounded HTTP fetch via ContractForge core",
            note="Public/no-auth bounded HTTP file reads use the generated Fabric notebook path; connector-specific E2E evidence is required before treating a new endpoint as production-ready.",
            renderable=True,
        )
    if _is_authenticated_http_with_placeholders(_source):
        return _supported(
            source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Fabric notebook bounded HTTP fetch via ContractForge core and Key Vault",
            note="Authenticated HTTP fetches are notebook-renderable when credentials use {{ secret:scope/key }} placeholders and the Fabric environment supplies Key Vault bindings; live evidence is still required.",
            renderable=True,
        )
    return _supported(
        source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Fabric notebook or Data Factory web activity",
        note="Authenticated HTTP fetches require {{ secret:scope/key }} credentials and Fabric environment Key Vault bindings before notebook rendering is allowed.",
        renderable=False,
    )


def _rest_api_classification(_source: dict[str, Any], source_type: str) -> FabricSourceClassification:
    if _is_public_bounded_http(_source):
        return _supported(
            source_type,
            status=SUPPORTED_WITH_WARNINGS,
            native_mapping="Fabric notebook bounded REST fetch via ContractForge core",
            note="Public/no-auth bounded REST reads use the generated Fabric notebook path; USGS REST/GeoJSON bronze-to-gold E2E has live Fabric evidence.",
            renderable=True,
        )
    if _is_authenticated_http_with_placeholders(_source):
        return _supported(
            source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Fabric notebook bounded REST fetch via ContractForge core and Key Vault",
            note="Authenticated REST reads are notebook-renderable when credentials use {{ secret:scope/key }} placeholders and the Fabric environment supplies Key Vault bindings; live evidence is still required.",
            renderable=True,
        )
    return _supported(
        source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Fabric Data Factory REST copy or notebook fetch",
        note="Authenticated REST reads require {{ secret:scope/key }} credentials and Fabric environment Key Vault bindings before notebook rendering is allowed.",
        renderable=False,
    )


def _incremental_classification(_source: dict[str, Any], source_type: str) -> FabricSourceClassification:
    return _supported(
        source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Fabric Data Factory incremental pipeline or notebook checkpoint",
        note="File-discovery and checkpoint semantics require runtime evidence.",
        renderable=False,
    )


def _bounded_stream_classification(_source: dict[str, Any], source_type: str) -> FabricSourceClassification:
    if _is_supported_available_now_kafka_with_placeholder_auth(_source):
        if _is_eventhubs_kafka_compatible(_source):
            return _supported(
                source_type,
                status=REVIEW_REQUIRED,
                native_mapping="Fabric notebook Event Hubs Kafka-compatible available-now catch-up through Spark Structured Streaming and Key Vault",
                note="Event Hubs Kafka-compatible available-now reads are notebook-renderable when a checkpoint is declared and SASL credentials use {{ secret:scope/key }} placeholders; live Fabric evidence exists for the documented smoke path.",
                renderable=True,
            )
        return _supported(
            source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Fabric notebook Kafka available-now catch-up through Spark Structured Streaming and Key Vault",
            note="Kafka available-now reads are notebook-renderable when a checkpoint is declared and SASL credentials use {{ secret:scope/key }} placeholders; live Fabric evidence is still required.",
            renderable=True,
        )
    if _is_supported_bounded_kafka_with_placeholder_auth(_source):
        if _is_eventhubs_kafka_compatible(_source):
            return _supported(
                source_type,
                status=REVIEW_REQUIRED,
                native_mapping="Fabric notebook Event Hubs Kafka-compatible bounded replay through Spark Kafka reader and Key Vault",
                note="Event Hubs Kafka-compatible bounded reads are notebook-renderable when finite offsets are declared and SASL credentials use {{ secret:scope/key }} placeholders; live Fabric evidence is still required for the bounded Event Hubs variant.",
                renderable=True,
            )
        return _supported(
            source_type,
            status=REVIEW_REQUIRED,
            native_mapping="Fabric notebook bounded Kafka replay through Spark Kafka reader and Key Vault",
            note="Bounded Kafka reads are notebook-renderable when finite offsets are declared and SASL credentials use {{ secret:scope/key }} placeholders; live Fabric evidence is still required.",
            renderable=True,
        )
    return _supported(
        source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Fabric Real-Time Intelligence or notebook bounded replay",
        note="Continuous and bounded replay semantics are not implemented in v0.",
        renderable=False,
    )


def _delta_share_classification(_source: dict[str, Any], source_type: str) -> FabricSourceClassification:
    return _supported(
        source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Delta Sharing client materialized into OneLake",
        note="Requires runtime dependency and credential review.",
        renderable=False,
    )


def _native_passthrough_classification(_source: dict[str, Any], source_type: str) -> FabricSourceClassification:
    return _supported(
        source_type,
        status=REVIEW_REQUIRED,
        native_mapping="Fabric native connector, shortcut or Data Factory activity",
        note="Native connector handoff must be reviewed per source system.",
        renderable=False,
    )


def _is_incremental_files(source: dict[str, Any]) -> bool:
    return str(source.get("type") or "").strip().lower() == "incremental_files"


def _is_plain_file_source(source: dict[str, Any]) -> bool:
    return _source_type(source) in FILE_SOURCE_TYPES


def _is_public_bounded_http(source: dict[str, Any]) -> bool:
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    if not str(source.get("url") or request.get("url") or source.get("path") or "").strip():
        return False
    auth = source.get("auth") if isinstance(source.get("auth"), dict) else {}
    auth_type = str(auth.get("type") or "none").strip().lower()
    if auth_type not in {"", "none"}:
        return False
    headers = request.get("headers") if isinstance(request.get("headers"), dict) else {}
    sensitive = {"authorization", "proxy-authorization", "x-api-key", "api-key", "apikey", "x-auth-token"}
    return not any(str(name).strip().lower() in sensitive for name in headers)


def _is_authenticated_http_with_placeholders(source: dict[str, Any]) -> bool:
    auth = source.get("auth") if isinstance(source.get("auth"), dict) else {}
    auth_type = str(auth.get("type") or "none").strip().lower()
    if auth_type in {"", "none"}:
        return False
    if auth_type == "bearer_token":
        return contains_secret_placeholder(auth.get("token"))
    if auth_type == "api_key":
        return bool(auth.get("header")) and contains_secret_placeholder(auth.get("value"))
    if auth_type == "basic":
        return bool(auth.get("username")) and contains_secret_placeholder(auth.get("password"))
    if auth_type == "oauth_client_credentials":
        return bool(auth.get("client_id")) and contains_secret_placeholder(auth.get("client_secret"))
    return False


def _is_supported_jdbc_with_placeholder_auth(source: dict[str, Any]) -> bool:
    connector = _source_type(source)
    url = str(source.get("url") or (source.get("options") or {}).get("url") or "").strip().lower()
    if _jdbc_family(source) not in {"sqlserver", "postgres"}:
        return False
    if connector == "jdbc" and not (url.startswith("jdbc:sqlserver:") or url.startswith("jdbc:postgresql:")):
        return False
    auth = source.get("auth") if isinstance(source.get("auth"), dict) else {}
    auth_type = str(auth.get("type") or ("basic" if auth else "none")).strip().lower()
    return auth_type == "basic" and bool(auth.get("username")) and contains_secret_placeholder(auth.get("password"))


def _jdbc_family(source: dict[str, Any]) -> str:
    connector = _source_type(source)
    url = str(source.get("url") or (source.get("options") or {}).get("url") or "").strip().lower()
    if connector == "sqlserver" or url.startswith("jdbc:sqlserver:"):
        return "sqlserver"
    if connector == "postgres" or url.startswith("jdbc:postgresql:"):
        return "postgres"
    return connector


def _is_supported_bounded_kafka_with_placeholder_auth(source: dict[str, Any]) -> bool:
    if _source_type(source) != "kafka_bounded":
        return False
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    if not str(source.get("bootstrap_servers") or options.get("kafka.bootstrap.servers") or "").strip():
        return False
    if not (source.get("topic") or source.get("topics") or source.get("assign")):
        return False
    if not _has_bounded_start(source, options) or not _has_bounded_end(source, options):
        return False
    protocol = str(options.get("kafka.security.protocol") or "").strip().upper()
    mechanism = str(options.get("kafka.sasl.mechanism") or "").strip().upper()
    jaas_config = options.get("kafka.sasl.jaas.config")
    return protocol == "SASL_SSL" and mechanism == "PLAIN" and contains_secret_placeholder(jaas_config)


def _is_supported_available_now_kafka_with_placeholder_auth(source: dict[str, Any]) -> bool:
    if _source_type(source) != "kafka_available_now":
        return False
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    if not str(source.get("bootstrap_servers") or options.get("kafka.bootstrap.servers") or "").strip():
        return False
    if not (source.get("topic") or source.get("topics") or source.get("assign")):
        return False
    if not str(source.get("checkpoint_location") or options.get("checkpointLocation") or "").strip():
        return False
    protocol = str(options.get("kafka.security.protocol") or "").strip().upper()
    mechanism = str(options.get("kafka.sasl.mechanism") or "").strip().upper()
    jaas_config = options.get("kafka.sasl.jaas.config")
    return protocol == "SASL_SSL" and mechanism == "PLAIN" and contains_secret_placeholder(jaas_config)


def _has_bounded_start(source: dict[str, Any], options: dict[str, Any]) -> bool:
    return any(
        value not in (None, "")
        for value in (
            source.get("starting_offsets"),
            source.get("starting_timestamp"),
            options.get("startingOffsets"),
            options.get("startingTimestamp"),
        )
    )


def _has_bounded_end(source: dict[str, Any], options: dict[str, Any]) -> bool:
    return any(
        value not in (None, "")
        for value in (
            source.get("ending_offsets"),
            source.get("ending_timestamp"),
            options.get("endingOffsets"),
            options.get("endingTimestamp"),
        )
    )


def _is_eventhubs_kafka_compatible(source: dict[str, Any]) -> bool:
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    system = str(source.get("system") or "").strip().lower()
    bootstrap = str(source.get("bootstrap_servers") or options.get("kafka.bootstrap.servers") or "").strip().lower()
    return system in {"azure_eventhubs", "eventhubs"} or ".servicebus.windows.net" in bootstrap


_CLASSIFICATION_RULES = (
    _SourceRule(_is_incremental_files, _incremental_classification),
    _SourceRule(_is_jdbc_source, _jdbc_classification),
    _SourceRule(is_catalog_source, _catalog_classification),
    _SourceRule(_is_object_storage_source, _file_classification),
    _SourceRule(is_http_file_source, _http_file_classification),
    _SourceRule(is_rest_api_connector, _rest_api_classification),
    _SourceRule(is_available_now_stream_source, _bounded_stream_classification),
    _SourceRule(is_bounded_stream_source, _bounded_stream_classification),
    _SourceRule(is_delta_share_source, _delta_share_classification),
    _SourceRule(_is_plain_file_source, _file_classification),
    _SourceRule(is_native_passthrough_source, _native_passthrough_classification),
)
