"""Databricks stabilization status reporting."""

from __future__ import annotations

import argparse
import json
from typing import Any


def add_stabilization_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    report = subcommands.add_parser(
        "stabilization-report",
        help="Print the Databricks adapter stabilization status for the supported v0.2.0 surface.",
    )
    report.add_argument(
        "--strict-final",
        action="store_true",
        help="Return a non-zero exit code while the documented stable-final claim is not satisfied.",
    )


def handle_stabilization(args: argparse.Namespace) -> int | None:
    if args.command != "stabilization-report":
        return None
    payload = databricks_stabilization_report()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.strict_final and payload["stable_final"] is not True:
        return 1
    return 0


def databricks_stabilization_report() -> dict[str, Any]:
    """Return the current Databricks adapter stabilization decision.

    ``supported_surface_ready`` covers the documented serverless Delta,
    Unity Catalog, evidence and contract-runtime available-now surface.
    ``stable_final`` is true for that scoped claim because full 1.0 GA,
    continuous streaming and broader provider matrices are separate gates.
    """

    return {
        "adapter": "contractforge-databricks",
        "subtarget": "databricks_serverless_delta",
        "classification": "STABLE_SUPPORTED_SURFACE",
        "supported_surface_ready": True,
        "stable_final": True,
        "release_candidate": "next-databricks-stable-surface",
        "gates": _gates(),
        "real_validation_projects": _real_validation_projects(),
        "accepted_review_boundaries": _accepted_review_boundaries(),
        "next_promotion_gates": [],
        "stability_criteria": "docs/specs/databricks-ga-criteria.md",
        "waiver_registry": "docs/specs/databricks-ga-waivers.md",
        "evidence_manifest": "docs/reports/databricks-stable-surface-evidence.json",
    }


def _gates() -> list[dict[str, str]]:
    return [
        {"id": "G0", "name": "local suite", "status": "PASS"},
        {"id": "G1", "name": "render and bundle artifacts", "status": "PASS"},
        {"id": "G2", "name": "runtime orchestration", "status": "PASS"},
        {"id": "G3", "name": "governance artifacts", "status": "PASS"},
        {"id": "G4", "name": "evidence and state tables", "status": "PASS"},
        {"id": "G5", "name": "available-now contract runtime", "status": "PASS"},
        {"id": "G6", "name": "platform parity", "status": "PASS_WITH_REVIEW_BOUNDARIES"},
        {"id": "G7", "name": "docs", "status": "PASS"},
    ]


def _real_validation_projects() -> list[dict[str, str]]:
    return [
        {"name": "databricks_reference_runtime_suite", "status": "PASS"},
        {"name": "databricks_same_contract_e2e", "status": "PASS"},
        {"name": "databricks_confluent_kafka_available_now", "status": "PASS"},
    ]


def _accepted_review_boundaries() -> list[dict[str, str]]:
    return [
        {
            "code": "DATABRICKS_FULL_GA_GATE",
            "area": "1.0.0 general availability",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "The stable-final claim covers the documented v0.2.0 serverless Delta surface. The broader 1.0 GA gate remains governed by the Databricks GA criteria.",
        },
        {
            "code": "DATABRICKS_CONTINUOUS_STREAMING_REVIEW",
            "area": "continuous streaming",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "The stable stream claim covers checkpointed available-now contract runtime. Unbounded continuous streaming remains outside stable-final.",
        },
        {
            "code": "DATABRICKS_PROVIDER_MATRIX_REVIEW",
            "area": "Kafka provider compatibility beyond validated Confluent Cloud",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "Confluent Cloud available-now contract runtime is validated. Additional Kafka-compatible providers require separate certification before provider-equivalence claims.",
        },
    ]
