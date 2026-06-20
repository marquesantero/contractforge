"""Snowflake-specific portability diagnostics layered on top of core planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from contractforge_core.planner import PlanningBlocker, PlanningWarning
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.contract_extensions import snowflake_extension_warnings
from contractforge_snowflake.preparation import unsupported_preparation_markers

_DATABRICKS_ONLY_SOURCES = {"autoloader", "cloudfiles", "cloud_files"}
_JDBC_SOURCES = {"jdbc", "postgres", "mysql", "sqlserver", "oracle", "redshift", "db2", "mariadb"}
_HTTP_FILE_SOURCES = {"http_file", "http_csv", "http_json", "http_text"}
_BOUNDED_STREAM_SOURCES = {"kafka_bounded", "eventhubs_bounded", "kafka_available_now", "eventhubs_available_now"}
_STAGED_FILE_SOURCES = {"staged_files", "stage_files", "snowflake_stage"}
_SUPPORTED_STAGED_FORMATS = {"csv", "json", "parquet"}


@dataclass(frozen=True)
class DiagnosticContext:
    contract: SemanticContract

    @property
    def source(self) -> dict:
        return self.contract.source.raw or {}

    @property
    def source_type(self) -> str:
        return str(self.source.get("type") or self.contract.source.kind or "").lower()

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


def snowflake_review_required_warnings(contract: SemanticContract) -> tuple[PlanningWarning, ...]:
    context = DiagnosticContext(contract)
    preparation_warnings = tuple(
        PlanningWarning(
            "SNOWFLAKE_PREPARATION_REVIEW_REQUIRED",
            f"{marker} is not implemented by the Snowflake SQL warehouse runtime yet.",
        )
        for marker in unsupported_preparation_markers(contract)
    )
    return tuple(rule.warning for rule in _REVIEW_RULES if rule.condition(context)) + preparation_warnings


def snowflake_planning_warnings(contract: SemanticContract) -> tuple[PlanningWarning, ...]:
    context = DiagnosticContext(contract)
    return tuple(rule.warning for rule in _WARNING_RULES if rule.condition(context)) + snowflake_extension_warnings(contract)


def _uses_databricks_only_source(context: DiagnosticContext) -> bool:
    return context.source_type in _DATABRICKS_ONLY_SOURCES or context.connector in _DATABRICKS_ONLY_SOURCES


def _uses_incremental_files(context: DiagnosticContext) -> bool:
    return context.source_type == "incremental_files"


def _uses_http_file(context: DiagnosticContext) -> bool:
    return context.source_type in _HTTP_FILE_SOURCES


def _uses_jdbc(context: DiagnosticContext) -> bool:
    return context.source_type in _JDBC_SOURCES or context.connector in _JDBC_SOURCES


def _uses_bounded_stream(context: DiagnosticContext) -> bool:
    return context.source_type in _BOUNDED_STREAM_SOURCES


def _uses_native_passthrough(context: DiagnosticContext) -> bool:
    return context.source_type == "native_passthrough"


def _uses_unsupported_staged_format(context: DiagnosticContext) -> bool:
    if context.source_type not in _STAGED_FILE_SOURCES:
        return False
    options = context.source.get("options") if isinstance(context.source.get("options"), dict) else {}
    source_format = context.source.get("format") or options.get("format")
    if source_format is None:
        return False
    return str(source_format).strip().lower() not in _SUPPORTED_STAGED_FORMATS


def _uses_expression_quality(context: DiagnosticContext) -> bool:
    return any(rule.rule == "expression" for rule in context.contract.quality)


def _uses_hash_diff(context: DiagnosticContext) -> bool:
    return context.contract.write.mode == "scd1_hash_diff"


def _uses_snapshot_soft_delete(context: DiagnosticContext) -> bool:
    return context.contract.write.mode == "snapshot_soft_delete"


def _uses_revoke_unmanaged_access(context: DiagnosticContext) -> bool:
    access = context.contract.governance.access if context.contract.governance else None
    if not isinstance(access, dict):
        return False
    policy = access.get("access_policy")
    if isinstance(policy, dict) and bool(policy.get("revoke_unmanaged", False)):
        return True
    return bool(access.get("revoke_unmanaged", False))


_BLOCKER_RULES = (
    BlockerRule(
        _uses_databricks_only_source,
        PlanningBlocker(
            "SNOWFLAKE_SOURCE_AUTOLOADER_UNSUPPORTED",
            "Databricks Auto Loader is not supported by the Snowflake adapter; use source.type='incremental_files'.",
        ),
    ),
)

_REVIEW_RULES = (
    WarningRule(
        _uses_incremental_files,
        PlanningWarning(
            "SNOWFLAKE_INCREMENTAL_FILES_REVIEW_REQUIRED",
            "incremental_files requires a Snowflake design choice: COPY_HISTORY, Snowpipe, directory tables or ContractForge state tables.",
        ),
    ),
    WarningRule(
        _uses_http_file,
        PlanningWarning(
            "SNOWFLAKE_HTTP_FILE_REVIEW_REQUIRED",
            "HTTP file ingestion should use a pre-stage or external-access/Snowpark design before runnable Snowflake artifacts are claimed.",
        ),
    ),
    WarningRule(
        _uses_jdbc,
        PlanningWarning(
            "SNOWFLAKE_JDBC_SOURCE_REVIEW_REQUIRED",
            "Snowflake is not the default JDBC extraction runtime; use a pre-staged source, native connector or reviewed Snowpark/external-access design.",
        ),
    ),
    WarningRule(
        _uses_bounded_stream,
        PlanningWarning(
            "SNOWFLAKE_STREAM_SOURCE_REVIEW_REQUIRED",
            "Kafka/Event Hubs semantics require Snowpipe Streaming or an external bridge design before bounded replay can be claimed.",
        ),
    ),
    WarningRule(
        _uses_native_passthrough,
        PlanningWarning(
            "SNOWFLAKE_NATIVE_PASSTHROUGH_REVIEW_REQUIRED",
            "native_passthrough requires a Snowflake connector, native app, marketplace or staged handoff design with explicit evidence boundaries.",
        ),
    ),
    WarningRule(
        _uses_unsupported_staged_format,
        PlanningWarning(
            "SNOWFLAKE_STAGED_FILE_FORMAT_REVIEW_REQUIRED",
            "Snowflake staged files support csv, json and parquet in the adapter runtime; other file formats require review.",
        ),
    ),
    WarningRule(
        _uses_revoke_unmanaged_access,
        PlanningWarning(
            "SNOWFLAKE_ACCESS_REVOKE_REVIEW_REQUIRED",
            "access.revoke_unmanaged is destructive in Snowflake because role inheritance and unmanaged grants require explicit review.",
        ),
    ),
)

_WARNING_RULES = (
    WarningRule(
        _uses_expression_quality,
        PlanningWarning(
            "SNOWFLAKE_EXPRESSION_QUALITY_SQL_DIALECT",
            "quality_rules.expressions are evaluated as Snowflake SQL predicates; validate dialect portability before production use.",
        ),
    ),
    WarningRule(
        _uses_hash_diff,
        PlanningWarning(
            "SNOWFLAKE_HASH_DIFF_SEMANTICS",
            "SCD1 hash diff maps to Snowflake hash staging plus MERGE; validate null, type and collation behavior for wide or mixed-type tables.",
        ),
    ),
    WarningRule(
        _uses_snapshot_soft_delete,
        PlanningWarning(
            "SNOWFLAKE_SNAPSHOT_SOFT_DELETE_SOURCE_COMPLETENESS",
            "snapshot_soft_delete requires a complete-source snapshot boundary; Snowflake MERGE can implement the write only after that contract assumption is proven.",
        ),
    ),
)
