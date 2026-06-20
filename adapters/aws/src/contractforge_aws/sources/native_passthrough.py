"""AWS native passthrough source planning artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from contractforge_core.connectors import native_passthrough_descriptor
from contractforge_aws.sources.native_passthrough_candidates import apply_candidates


@dataclass(frozen=True)
class _NativeTargetRecommendation:
    systems: frozenset[str]
    targets: tuple[str, ...]
    notes: tuple[str, ...]


_RECOMMENDATIONS = (
    _NativeTargetRecommendation(
        systems=frozenset({"salesforce", "zendesk", "marketo", "slack"}),
        targets=("appflow", "glue_native_connector"),
        notes=("Prefer AppFlow when incremental SaaS extraction and managed auth preserve the contract intent.",),
    ),
    _NativeTargetRecommendation(
        systems=frozenset({"mysql", "postgres", "postgresql", "oracle", "sqlserver", "mariadb"}),
        targets=("dms", "glue_jdbc"),
        notes=("Prefer the portable JDBC source unless CDC replication is required.",),
    ),
    _NativeTargetRecommendation(
        systems=frozenset({"sap", "sap_odata", "odata", "workday", "servicenow"}),
        targets=("glue_native_connector", "partner_connector", "appflow_if_supported"),
        notes=("Keep vendor protocol handling in AWS-native or partner-managed connectors.",),
    ),
)
_DEFAULT_TARGETS = ("glue_custom_connector", "appflow_if_supported", "dms_if_database_replication")


def render_native_passthrough_plan(source: dict[str, Any]) -> str:
    descriptor = native_passthrough_descriptor(source)
    recommendation = _recommendation(str(descriptor["system"]))
    payload = {
        "kind": "aws_native_passthrough_plan",
        **descriptor,
        "status": "REVIEW_REQUIRED",
        "recommended_aws_targets": list(recommendation.targets),
        "recommended_aws_paths": [_target_profile(target) for target in recommendation.targets],
        "review_only_apply_candidates": apply_candidates(recommendation.targets, descriptor),
        "contract_mapping": _contract_mapping(descriptor),
        "review_required_inputs": _review_required_inputs(recommendation.targets),
        "evidence_strategy": {
            "handoff_status": "record in ctrl_ingestion_runs and ctrl_ingestion_metadata",
            "native_service_run": "record external flow/task/job identifiers in source_metadata_json",
            "landing_validation": "validate landed objects before downstream Glue/Iceberg ingestion",
        },
        "unsupported_claims": [
            "This artifact does not execute AppFlow, DMS or Glue connector APIs.",
            "This artifact does not certify SaaS API pagination, deletes, CDC or schema drift semantics.",
            "A reviewed AWS-native design must preserve the ContractForge source, watermark, quality and evidence intent.",
        ],
        "notes": [
            *recommendation.notes,
            "Do not implement proprietary SaaS API algorithms inside contractforge_aws when AWS-native services preserve the intent.",
            "Application must stay adapter-owned and auditable; this artifact is a review/apply handoff, not core execution.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _recommendation(system: str) -> _NativeTargetRecommendation:
    normalized = system.lower()
    return next(
        (recommendation for recommendation in _RECOMMENDATIONS if normalized in recommendation.systems),
        _NativeTargetRecommendation(frozenset(), _DEFAULT_TARGETS, ()),
    )


def _target_profile(target: str) -> dict[str, Any]:
    return dict(_TARGET_PROFILES.get(target, _TARGET_PROFILES["glue_custom_connector"]))


def _contract_mapping(descriptor: dict[str, Any]) -> dict[str, Any]:
    return {
        "source.system": descriptor["system"],
        "source.object": descriptor["object"],
        "source.watermark": descriptor.get("watermark", {}),
        "source.auth": "adapter-owned secret resolution; rendered descriptor redacts secret fields",
        "target": "native service should land to S3 or a Glue-readable catalog/table before ContractForge writes the governed target",
    }


def _review_required_inputs(targets: tuple[str, ...]) -> list[str]:
    values: list[str] = [
        "target S3 landing location and encryption policy",
        "native service IAM role and network boundary",
        "source auth ownership and secret rotation policy",
        "incremental watermark, delete handling and schema drift behavior",
    ]
    for target in targets:
        values.extend(_TARGET_REVIEW_INPUTS.get(target, ()))
    return sorted(set(values))


_TARGET_PROFILES: dict[str, dict[str, Any]] = {
    "appflow": {
        "service": "Amazon AppFlow",
        "fit": "managed SaaS extraction to S3 when the source application and incremental trigger preserve intent",
        "expected_artifacts": ("flow definition", "connector profile", "S3 destination", "field mappings"),
        "apply_boundary": "review/apply outside core; future runtime helper may call AppFlow APIs",
    },
    "appflow_if_supported": {
        "service": "Amazon AppFlow",
        "fit": "candidate only if the specific application/object is supported in the target AWS region",
        "expected_artifacts": ("flow definition", "connector profile", "S3 destination", "field mappings"),
        "apply_boundary": "review/apply outside core",
    },
    "dms": {
        "service": "AWS Database Migration Service",
        "fit": "database full-load or CDC replication where JDBC batch is insufficient",
        "expected_artifacts": ("source endpoint", "target endpoint", "replication config/task", "table mappings"),
        "apply_boundary": "review/apply outside core; ContractForge consumes landed output or replicated target",
    },
    "dms_if_database_replication": {
        "service": "AWS Database Migration Service",
        "fit": "candidate only when the passthrough source is a supported database replication source",
        "expected_artifacts": ("source endpoint", "target endpoint", "replication config/task", "table mappings"),
        "apply_boundary": "review/apply outside core",
    },
    "glue_jdbc": {
        "service": "AWS Glue JDBC",
        "fit": "Glue-native JDBC job when the source can be represented as batch/incremental JDBC",
        "expected_artifacts": ("Glue connection", "job bookmark keys", "generated Glue job"),
        "apply_boundary": "prefer portable jdbc source when possible",
    },
    "glue_native_connector": {
        "service": "AWS Glue connector",
        "fit": "AWS-provided or Marketplace connector when connector semantics preserve source intent",
        "expected_artifacts": ("Glue connection", "connector options", "generated Glue job or handoff job"),
        "apply_boundary": "review connector licensing, auth, networking and runtime options",
    },
    "glue_custom_connector": {
        "service": "AWS Glue custom connector",
        "fit": "last-resort connector-owned extraction for sources not covered by portable sources or native managed services",
        "expected_artifacts": ("connector artifact", "Glue connection", "connector options", "review report"),
        "apply_boundary": "connector implementation remains outside core semantics",
    },
    "partner_connector": {
        "service": "AWS partner connector",
        "fit": "partner-managed connector for proprietary applications with complex API/auth behavior",
        "expected_artifacts": ("subscription/license", "connection profile", "landing contract", "review report"),
        "apply_boundary": "review vendor SLA, security model and evidence handoff",
    },
}

_TARGET_REVIEW_INPUTS: dict[str, tuple[str, ...]] = {
    "appflow": ("AppFlow connector profile", "AppFlow trigger mode", "AppFlow field mappings"),
    "appflow_if_supported": ("AppFlow application availability", "AppFlow connector profile"),
    "dms": ("DMS endpoint settings", "DMS replication mode", "DMS table mappings"),
    "dms_if_database_replication": ("DMS source/target support proof", "DMS replication mode"),
    "glue_jdbc": ("Glue connection", "JDBC driver availability", "bookmark key validation"),
    "glue_native_connector": ("Glue connector subscription or native connector config", "connector option mapping"),
    "glue_custom_connector": ("custom connector artifact", "connector option mapping", "connector support owner"),
    "partner_connector": ("partner connector contract", "vendor support and licensing review"),
}
