"""AWS-specific portability diagnostics layered on top of core planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from contractforge_core.connectors import is_available_now_stream_source, is_bounded_stream_source, is_delta_share_source
from contractforge_core.planner import PlanningBlocker, PlanningWarning
from contractforge_core.semantic import SemanticContract
from contractforge_aws.sources.classification import source_requires_runtime_file_config

_DATABRICKS_ONLY_SOURCES = {"autoloader", "cloudfiles", "cloud_files"}


@dataclass(frozen=True)
class DiagnosticContext:
    contract: SemanticContract

    @property
    def source(self) -> dict:
        return self.contract.source.raw or {}

    @property
    def source_type(self) -> str:
        return str(self.source.get("type") or "").lower()

    @property
    def connector(self) -> str:
        return str(self.source.get("connector") or "").lower()


@dataclass(frozen=True)
class BlockerRule:
    condition: Callable[[DiagnosticContext], bool]
    blocker: PlanningBlocker


@dataclass(frozen=True)
class WarningRule:
    condition: Callable[[DiagnosticContext], bool]
    warning: PlanningWarning


def unsupported_source_blockers(contract: SemanticContract) -> tuple[PlanningBlocker, ...]:
    context = DiagnosticContext(contract)
    return tuple(rule.blocker for rule in _BLOCKER_RULES if rule.condition(context))


def aws_planning_warnings(contract: SemanticContract) -> tuple[PlanningWarning, ...]:
    context = DiagnosticContext(contract)
    return tuple(rule.warning for rule in _WARNING_RULES if rule.condition(context))


def _uses_databricks_only_source(context: DiagnosticContext) -> bool:
    return context.source_type in _DATABRICKS_ONLY_SOURCES or context.connector in _DATABRICKS_ONLY_SOURCES


def _uses_available_now(context: DiagnosticContext) -> bool:
    operations = context.contract.operations
    return is_available_now_stream_source(context.source) or bool(operations and operations.available_now_streaming)


def _uses_unvalidated_available_now_provider(context: DiagnosticContext) -> bool:
    if not _uses_available_now(context):
        return False
    source_system = str(context.source.get("system") or "").lower()
    bootstrap_servers = str(context.source.get("bootstrap_servers") or "").lower()
    is_eventhubs_kafka = source_system in {"azure_eventhubs", "eventhubs"} or ".servicebus.windows.net" in bootstrap_servers
    return not (context.source_type == "kafka_available_now" and is_eventhubs_kafka)


def _uses_expression_quality(context: DiagnosticContext) -> bool:
    return any(rule.rule == "expression" for rule in context.contract.quality)


def _hash_diff_missing_merge_keys(context: DiagnosticContext) -> bool:
    return context.contract.write.mode == "scd1_hash_diff" and not context.contract.write.merge_keys


_BLOCKER_RULES = (
    BlockerRule(
        _uses_databricks_only_source,
        PlanningBlocker(
            "AWS_SOURCE_AUTOLOADER_UNSUPPORTED",
            "Databricks Auto Loader is not supported by the AWS adapter; use source.type='incremental_files'.",
        ),
    ),
    BlockerRule(
        _hash_diff_missing_merge_keys,
        PlanningBlocker(
            "AWS_HASH_DIFF_MERGE_KEYS_REQUIRED",
            "AWS Glue Iceberg scd1_hash_diff requires merge_keys for row identity. Use hash_keys for explicit content hashing or hash_strategy=all_columns_except for wide tables.",
        ),
    ),
)


_WARNING_RULES = (
    WarningRule(
        _uses_expression_quality,
        PlanningWarning(
            "AWS_EXPRESSION_QUALITY_SPARK_SQL",
            "quality_rules.expressions are evaluated as Spark SQL filters in the Glue job, not as Glue DQDL; "
            "validate expression dialect portability before production use.",
        ),
    ),
    WarningRule(
        lambda context: context.contract.write.mode == "scd1_hash_diff",
        PlanningWarning(
            "AWS_HASH_DIFF_PERFORMANCE_UNVALIDATED",
            "SCD1 hash diff maps to Iceberg merge plus hash staging; validate Glue/Iceberg performance and concurrency before production use.",
        ),
    ),
    WarningRule(
        lambda context: context.source_type == "incremental_files",
        PlanningWarning(
            "AWS_INCREMENTAL_FILES_STRATEGY_REVIEW",
            "incremental_files renders an S3 Glue-bookmark read; register the job with "
            "--job-bookmark-option job-bookmark-enable (enable_job_bookmark=True) so progress persists across runs.",
        ),
    ),
    WarningRule(
        lambda context: context.source_type == "native_passthrough",
        PlanningWarning(
            "AWS_NATIVE_PASSTHROUGH_REVIEW",
            "native_passthrough requires an AWS-native service design such as AppFlow or DMS before runnable artifacts are generated.",
        ),
    ),
    WarningRule(
        lambda context: source_requires_runtime_file_config(context.source),
        PlanningWarning(
            "AWS_SOURCE_RUNTIME_CONFIG_REQUIRED",
            "This source is renderable in Glue Spark but requires reviewed runtime connector/package and credential configuration.",
        ),
    ),
    WarningRule(
        lambda context: is_bounded_stream_source(context.source) or is_delta_share_source(context.source),
        PlanningWarning(
            "AWS_SOURCE_CONNECTOR_PACKAGE_REQUIRED",
            "This source renders in Glue Spark but requires the matching connector jar/package to be supplied to the Glue job.",
        ),
    ),
    WarningRule(
        _uses_unvalidated_available_now_provider,
        PlanningWarning(
            "AWS_AVAILABLE_NOW_STREAMING_PROVIDER_REVIEW",
            "available_now renders a Glue structured-streaming job. The AWS adapter has real validation for "
            "Azure Event Hubs through the Kafka protocol; validate checkpoint, connector package and write "
            "idempotency semantics before using another Kafka/Event Hubs provider in production.",
        ),
    ),
)
