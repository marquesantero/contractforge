"""AWS source connector classification.

This module is adapter-owned: it maps portable core connector semantics to the
AWS Glue/Iceberg rendering surface without teaching the core anything about AWS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from contractforge_core.connectors import (
    JDBC_CONNECTORS,
    is_available_now_stream_source,
    is_bounded_stream_source,
    is_catalog_source,
    is_delta_share_source,
    is_file_source,
    is_http_file_source,
    is_rest_api_connector,
)
from contractforge_aws.sources.interpret import incremental_files_is_bookmark_renderable, is_incremental_file_source

SUPPORTED = "SUPPORTED"
SUPPORTED_WITH_WARNINGS = "SUPPORTED_WITH_WARNINGS"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
UNSUPPORTED = "UNSUPPORTED"
_RUNTIME_CONFIG_FILE_TYPES = frozenset({"delta", "xml"})
_RUNTIME_CONFIG_STORAGE_TYPES = frozenset({"adls", "azure_blob", "gcs", "blob", "object_storage"})


@dataclass(frozen=True)
class AWSSourceClassification:
    source_type: str
    status: str
    native_mapping: str | None
    note: str
    renderable: bool


@dataclass(frozen=True)
class _SourceRule:
    matches: Callable[[dict[str, Any]], bool]
    classify: Callable[[dict[str, Any], str], AWSSourceClassification]


def classify_aws_source(source: dict[str, Any] | str) -> AWSSourceClassification:
    """Classify an AWS source for documentation and render routing."""

    payload = {"type": source} if isinstance(source, str) else dict(source)
    source_type = str(payload.get("connector") or payload.get("type") or "").strip().lower()
    for rule in _CLASSIFICATION_RULES:
        if rule.matches(payload):
            return rule.classify(payload, source_type)
    return AWSSourceClassification(
        source_type=source_type,
        status=UNSUPPORTED,
        native_mapping=None,
        note="No AWS source renderer is declared for this connector.",
        renderable=False,
    )


def is_aws_source_renderable(source: dict[str, Any]) -> bool:
    return classify_aws_source(source).renderable


def source_requires_runtime_file_config(source: dict[str, Any]) -> bool:
    source_type = str(source.get("type") or "").strip().lower()
    connector = str(source.get("connector") or "").strip().lower()
    declared_format = str(source.get("format") or "").strip().lower()
    return bool(
        {source_type, connector, declared_format} & (_RUNTIME_CONFIG_FILE_TYPES | _RUNTIME_CONFIG_STORAGE_TYPES)
    )


def _is_jdbc_source(source: dict[str, Any]) -> bool:
    connector = source.get("connector") or source.get("type")
    return connector in JDBC_CONNECTORS or source.get("type") == "jdbc"


def _is_native_passthrough(source: dict[str, Any]) -> bool:
    return str(source.get("type") or "").strip().lower() == "native_passthrough"


def _incremental_classification(source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    renderable = incremental_files_is_bookmark_renderable(source)
    return AWSSourceClassification(
        source_type=source_type,
        status=SUPPORTED if renderable else REVIEW_REQUIRED,
        native_mapping="AWS Glue job bookmarks",
        note="Requires S3 path and bookmark-eligible format.",
        renderable=renderable,
    )


def _supported_classification(
    source_type: str,
    *,
    native_mapping: str,
    note: str,
    status: str = SUPPORTED,
    renderable: bool = True,
) -> AWSSourceClassification:
    return AWSSourceClassification(
        source_type=source_type,
        status=status,
        native_mapping=native_mapping,
        note=note,
        renderable=renderable,
    )


def _jdbc_classification(_source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    return _supported_classification(
        source_type,
        native_mapping="Spark JDBC reader in Glue",
        note="Core builds JDBC options; AWS resolves secrets.",
    )


def _catalog_classification(_source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    return _supported_classification(
        source_type,
        native_mapping="Spark catalog/sql in Glue",
        note="Glue Catalog/Iceberg runtime mapping.",
    )


def _http_file_classification(_source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    return _supported_classification(
        source_type,
        native_mapping="Core HTTP file fetch + Glue Spark materialization",
        note="Fetch algorithm lives in core.",
    )


def _rest_api_classification(_source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    return _supported_classification(
        source_type,
        native_mapping="Core REST client + Glue Spark JSON materialization",
        note="Bounded REST only.",
    )


def _available_now_classification(source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    options = source.get("options", {})
    checkpoint = source.get("checkpoint_location")
    if isinstance(options, dict):
        checkpoint = checkpoint or options.get("checkpointLocation")
    renderable = bool(str(checkpoint or "").strip())
    return _supported_classification(
        source_type,
        status=SUPPORTED_WITH_WARNINGS if renderable else REVIEW_REQUIRED,
        native_mapping="Spark readStream availableNow in Glue",
        note="Requires checkpoint and append-compatible write mode.",
        renderable=renderable,
    )


def _bounded_stream_classification(_source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    return _supported_classification(
        source_type,
        status=SUPPORTED_WITH_WARNINGS,
        native_mapping="Spark bounded kafka/eventhubs reader in Glue",
        note="Connector jars must be supplied.",
    )


def _delta_share_classification(_source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    return _supported_classification(
        source_type,
        status=SUPPORTED_WITH_WARNINGS,
        native_mapping="Delta Sharing Spark connector in Glue",
        note="Connector jar must be supplied.",
    )


def _file_classification(source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    if source_requires_runtime_file_config(source):
        return _supported_classification(
            source_type,
            status=SUPPORTED_WITH_WARNINGS,
            native_mapping="Spark file reader in Glue with runtime connector configuration",
            note="Renderable, but AWS Glue needs the matching connector/package and credentials configured.",
        )
    return _supported_classification(
        source_type,
        native_mapping="Spark file reader in Glue",
        note="Format and reader options are core-normalized.",
    )


def _native_passthrough_classification(_source: dict[str, Any], source_type: str) -> AWSSourceClassification:
    return _supported_classification(
        source_type,
        status=REVIEW_REQUIRED,
        native_mapping="AWS native connector handoff",
        note="Use AppFlow/DMS/vendor services by review.",
        renderable=False,
    )


_CLASSIFICATION_RULES = (
    _SourceRule(is_incremental_file_source, _incremental_classification),
    _SourceRule(_is_jdbc_source, _jdbc_classification),
    _SourceRule(is_catalog_source, _catalog_classification),
    _SourceRule(is_http_file_source, _http_file_classification),
    _SourceRule(is_rest_api_connector, _rest_api_classification),
    _SourceRule(is_available_now_stream_source, _available_now_classification),
    _SourceRule(is_bounded_stream_source, _bounded_stream_classification),
    _SourceRule(is_delta_share_source, _delta_share_classification),
    _SourceRule(is_file_source, _file_classification),
    _SourceRule(_is_native_passthrough, _native_passthrough_classification),
)
