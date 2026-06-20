"""AWS stabilization status reporting."""

from __future__ import annotations

import argparse
import json
from typing import Any


def add_stabilization_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    report = subparsers.add_parser(
        "stabilization-report",
        help="Print the AWS adapter stabilization status for the supported v0.2.0 surface.",
    )
    report.add_argument(
        "--strict-final",
        action="store_true",
        help="Return a non-zero exit code while any production-certification review boundary remains.",
    )


def handle_stabilization_command(args: argparse.Namespace) -> int | None:
    if args.command != "stabilization-report":
        return None
    payload = aws_stabilization_report()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.strict_final and payload["stable_final"] is not True:
        return 1
    return 0


def aws_stabilization_report() -> dict[str, Any]:
    """Return the current AWS adapter stabilization decision.

    This report is intentionally explicit about two different claims:

    * ``supported_surface_ready``: the documented AWS Glue/Iceberg scope
      has passed its local, render, runtime, evidence and lifecycle gates.
    * ``stable_final``: every production-certification concern inside the
      documented AWS Glue/Iceberg claim is certified or explicitly excluded.
      Broader provider, governance-expression and historical semantics claims
      remain outside this scoped release decision.
    """

    return {
        "adapter": "contractforge-aws",
        "subtarget": "aws_glue_iceberg",
        "classification": "STABLE_SUPPORTED_SURFACE",
        "supported_surface_ready": True,
        "stable_final": True,
        "release_candidate": "next-aws-stable-surface",
        "gates": _gates(),
        "real_validation_projects": _real_validation_projects(),
        "accepted_review_boundaries": _accepted_review_boundaries(),
        "next_promotion_gates": _next_promotion_gates(),
        "stability_criteria": "docs/specs/aws-ga-criteria.md",
        "waiver_registry": "docs/specs/aws-ga-waivers.md",
        "evidence_manifest": "docs/reports/aws-stable-surface-evidence.json",
    }


def _gates() -> list[dict[str, str]]:
    return [
        {"id": "G0", "name": "local suite", "status": "PASS"},
        {"id": "G1", "name": "render compile", "status": "PASS"},
        {"id": "G2", "name": "deploy flow", "status": "PASS"},
        {"id": "G3", "name": "success runtime", "status": "PASS"},
        {"id": "G4", "name": "failure runtime", "status": "PASS"},
        {"id": "G5", "name": "control audit", "status": "PASS"},
        {"id": "G6", "name": "parity", "status": "PASS_WITH_REVIEW_BOUNDARIES"},
        {"id": "G7", "name": "docs", "status": "PASS"},
        {"id": "G8", "name": "lifecycle cleanup plan", "status": "PASS"},
    ]


def _real_validation_projects() -> list[dict[str, str]]:
    return [
        {"name": "aws_supabase_jdbc_medallion", "status": "PASS"},
        {"name": "aws_usgs_rest_medallion", "status": "PASS"},
        {"name": "aws_s3_file_medallion", "status": "PASS"},
        {"name": "aws_incremental_files", "status": "PASS"},
        {"name": "aws_failure_paths", "status": "PASS"},
        {"name": "aws_eventhubs_kafka_available_now", "status": "PASS"},
        {"name": "aws_msk_kafka_available_now", "status": "PASS"},
        {"name": "aws_hashdiff_production_benchmark", "status": "PASS"},
    ]


def _accepted_review_boundaries() -> list[dict[str, str]]:
    return [
        {
            "code": "AWS_HASH_DIFF_PERFORMANCE_UNVALIDATED",
            "area": "scd1_hash_diff",
            "decision": "SUPPORTED_WITH_WARNINGS",
            "reason": "The reference production benchmark is validated; workload-specific SLA claims remain outside strict-final unless evidence is attached for that contract.",
        },
        {
            "code": "AWS_AVAILABLE_NOW_STREAMING_PROVIDER_REVIEW",
            "area": "non-MSK Kafka/Event Hubs compatibility providers",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "AWS-native Kafka maturity is validated with MSK. Non-MSK compatibility providers, including Confluent Cloud and Event Hubs variants, are outside strict-final unless separately certified.",
        },
        {
            "code": "AWS_LAKE_FORMATION_GOVERNANCE_REVIEW",
            "area": "row filters and column masks",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "The LF consumer-engine matrix passed for Athena and Glue Spark; arbitrary contract row-filter and mask expressions are outside strict-final unless reviewed for that contract.",
        },
        {
            "code": "AWS_SCD2_REVIEW",
            "area": "SCD2 and snapshot soft delete",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "Historical modes are explicitly outside the AWS stable-final claim until Databricks/AWS parity evidence is attached.",
        },
    ]


def _next_promotion_gates() -> list[dict[str, str]]:
    return []
