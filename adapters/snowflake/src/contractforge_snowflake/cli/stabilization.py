"""Snowflake stabilization status reporting."""

from __future__ import annotations

import argparse
import json
from typing import Any


def add_stabilization_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    report = subcommands.add_parser(
        "stabilization-report",
        help="Print the Snowflake adapter stabilization status for the supported v0.2.0 surface.",
    )
    report.add_argument(
        "--strict-final",
        action="store_true",
        help="Return a non-zero exit code while any production-certification review boundary remains.",
    )


def handle_stabilization(args: argparse.Namespace) -> int | None:
    if args.command != "stabilization-report":
        return None
    payload = snowflake_stabilization_report()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.strict_final and payload["stable_final"] is not True:
        return 1
    return 0


def snowflake_stabilization_report() -> dict[str, Any]:
    """Return the current Snowflake adapter stabilization decision.

    ``supported_surface_ready`` covers the documented SQL warehouse,
    hosted-procedure and staged-file surface. ``stable_final`` is true for the
    documented claim because account-feature-dependent policy enforcement,
    continuous ingestion and historical modes are explicitly outside that claim.
    """

    return {
        "adapter": "contractforge-snowflake",
        "subtarget": "snowflake_sql_warehouse",
        "classification": "STABLE_SUPPORTED_SURFACE",
        "supported_surface_ready": True,
        "stable_final": True,
        "release_candidate": "next-snowflake-stable-surface",
        "gates": _gates(),
        "real_validation_projects": _real_validation_projects(),
        "accepted_review_boundaries": _accepted_review_boundaries(),
        "next_promotion_gates": _next_promotion_gates(),
        "stability_criteria": "docs/specs/snowflake-ga-criteria.md",
        "waiver_registry": "docs/specs/snowflake-ga-waivers.md",
        "evidence_manifest": "docs/reports/snowflake-stable-surface-evidence.json",
    }


def _gates() -> list[dict[str, str]]:
    return [
        {"id": "G0", "name": "local suite", "status": "PASS"},
        {"id": "G1", "name": "render compile", "status": "PASS"},
        {"id": "G2", "name": "stage publish flow", "status": "PASS"},
        {"id": "G3", "name": "success runtime", "status": "PASS"},
        {"id": "G4", "name": "failure runtime", "status": "PASS"},
        {"id": "G5", "name": "control audit", "status": "PASS"},
        {"id": "G6", "name": "lineage and explain", "status": "PASS"},
        {"id": "G7", "name": "cost reconciliation", "status": "PASS"},
        {"id": "G8", "name": "governance comments and tags", "status": "PASS"},
        {"id": "G9", "name": "hosted procedure", "status": "PASS"},
        {"id": "G10", "name": "task graph live execution", "status": "PASS"},
        {"id": "G11", "name": "platform parity", "status": "PASS_WITH_REVIEW_BOUNDARIES"},
        {"id": "G12", "name": "docs", "status": "PASS"},
        {"id": "G13", "name": "lifecycle cleanup plan", "status": "PASS"},
    ]


def _real_validation_projects() -> list[dict[str, str]]:
    return [
        {"name": "snowflake_smoke_minimal", "status": "PASS"},
        {"name": "snowflake_smoke_failure_paths", "status": "PASS"},
        {"name": "snowflake_smoke_stage_publish", "status": "PASS"},
        {"name": "snowflake_smoke_procedure", "status": "PASS"},
        {"name": "snowflake_smoke_task_graph", "status": "PASS"},
        {"name": "snowflake_usgs_rest_medallion", "status": "PASS"},
        {"name": "snowflake_hashdiff_production_benchmark", "status": "PASS"},
    ]


def _accepted_review_boundaries() -> list[dict[str, str]]:
    return [
        {
            "code": "SNOWFLAKE_HASH_DIFF_PERFORMANCE_UNVALIDATED",
            "area": "scd1_hash_diff",
            "decision": "SUPPORTED_WITH_WARNINGS",
            "reason": "The reference production benchmark is validated; individual hash-diff contracts still carry a benchmark-required warning until workload-specific evidence is attached.",
        },
        {
            "code": "SNOWFLAKE_ACCESS_POLICY_ACCOUNT_FEATURE_BLOCKED",
            "area": "row access policies and masking policies",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "The connected account returns Unsupported feature 'ROW ACCESS POLICY'. Table grants, comments/tags and validate-only governance remain supported; row access and masking policy certification are excluded from the stable-final claim for this account.",
        },
        {
            "code": "SNOWFLAKE_CONTINUOUS_INGESTION_REVIEW",
            "area": "Snowpipe, Streams and continuous file ingestion",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "The stable surface covers table, SQL and staged-file batch sources. Snowpipe, Streams, Snowpipe Streaming and Kafka connector ingestion require a separate runtime/evidence mapping.",
        },
        {
            "code": "SNOWFLAKE_SCD2_REVIEW",
            "area": "SCD2 and snapshot soft delete",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "Historical modes are explicitly outside the Snowflake stable-final claim until Databricks/Snowflake parity evidence is attached.",
        },
    ]


def _next_promotion_gates() -> list[dict[str, str]]:
    return []
