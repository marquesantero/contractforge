"""Review boundary derivation for AWS deployment manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from contractforge_core.connectors import is_available_now_stream_source, is_bounded_stream_source, is_delta_share_source
from contractforge_core.semantic import SemanticContract
from contractforge_aws.sources import source_requires_rds_iam, source_requires_secret_resolver
from contractforge_aws.sources.classification import source_requires_runtime_file_config

_BASE_BOUNDARIES = (
    "IAM role permissions for Glue, S3, CloudWatch Logs, Secrets Manager and optional RDS IAM.",
    "S3 artifact, warehouse and temporary paths, including encryption and bucket policy.",
    "Glue Catalog database/table ownership and Iceberg warehouse location.",
)


@dataclass(frozen=True)
class BoundaryContext:
    contract: SemanticContract | None
    artifacts: dict[str, str]

    @property
    def source(self) -> dict:
        return self.contract.source.raw if self.contract else {}


@dataclass(frozen=True)
class BoundaryRule:
    condition: Callable[[BoundaryContext], bool]
    message: str


def review_boundaries(contract: SemanticContract | None, artifacts: dict[str, str]) -> list[str]:
    context = BoundaryContext(contract=contract, artifacts=artifacts)
    dynamic = (rule.message for rule in _BOUNDARY_RULES if rule.condition(context))
    return [*_BASE_BOUNDARIES, *dynamic]


def _has_artifact_suffix(context: BoundaryContext, suffix: str) -> bool:
    return any(name.endswith(suffix) for name in context.artifacts)


def _has_governance(context: BoundaryContext) -> bool:
    return _has_artifact_suffix(context, ".lakeformation.json") or bool(context.contract and context.contract.governance)


def _needs_connector_package(context: BoundaryContext) -> bool:
    source = context.source
    return is_bounded_stream_source(source) or is_available_now_stream_source(source) or is_delta_share_source(source)


_BOUNDARY_RULES = (
    BoundaryRule(
        lambda context: source_requires_secret_resolver(context.source),
        "Secrets Manager secret ARNs and rotation policy for declared secret placeholders.",
    ),
    BoundaryRule(
        lambda context: source_requires_rds_iam(context.source),
        "RDS IAM db_resource_id mapping and database user grant review.",
    ),
    BoundaryRule(
        lambda context: source_requires_runtime_file_config(context.source),
        "Glue runtime connector/package and credential configuration for this source.",
    ),
    BoundaryRule(
        _needs_connector_package,
        "Glue connector jar/package availability and runtime dependency review.",
    ),
    BoundaryRule(
        _has_governance,
        "Lake Formation grants, data filters, column masking and consumer-engine compatibility.",
    ),
    BoundaryRule(
        lambda context: _has_artifact_suffix(context, ".native_passthrough.json"),
        "AWS-native service handoff such as AppFlow, DMS or partner connector configuration.",
    ),
    BoundaryRule(
        lambda context: _has_artifact_suffix(context, ".glue_job.todo.md"),
        "Review-required semantics blocked runnable Glue job generation.",
    ),
)
