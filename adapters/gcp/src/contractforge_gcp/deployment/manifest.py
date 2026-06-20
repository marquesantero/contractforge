"""Render deterministic GCP BigQuery deployment manifests."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.planner import PlanningResult
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.capabilities import GCP_SUBTARGET_BIGQUERY
from contractforge_gcp.dataplex import has_dataplex_aspect_plan, has_dataplex_lineage_plan
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import public_mode, target_table_id
from contractforge_gcp.sources import REVIEW_REQUIRED, UNSUPPORTED, classify_gcp_source


def render_gcp_deployment_manifest(
    *,
    contract: SemanticContract,
    environment: GCPEnvironment,
    planning: PlanningResult | None,
    artifacts: dict[str, str],
) -> str:
    """Describe how rendered BigQuery artifacts can be applied for one contract."""

    deployment_status = _deployment_status(planning)
    payload = {
        "kind": "contractforge.gcp.deployment_manifest.v1",
        "adapter": "contractforge-gcp",
        "subtarget": GCP_SUBTARGET_BIGQUERY,
        "status": deployment_status,
        "planning_status": planning.status if planning else None,
        "execution_ready": deployment_status == "supported",
        "target": {
            "project_id": environment.project_id,
            "location": environment.location or "US",
            "table": target_table_id(contract, environment),
            "write_mode": public_mode(contract.write.mode),
        },
        "evidence_dataset": environment.evidence_dataset or environment.dataset,
        "execution_model": "single_contract_bigquery_smoke",
        "orchestration": {
            "included": False,
            "reason": (
                "Live Workflows, Cloud Run Jobs, Composer DAGs and scheduled-query "
                "deployment runners remain outside the stable GCP surface until separately certified."
            ),
        },
        "apply_order": _apply_order(artifacts, deployment_status=deployment_status),
        "review_boundaries": _review_boundaries(contract),
        "artifact_summary": _artifact_summary(artifacts),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _deployment_status(planning: PlanningResult | None) -> str:
    if planning is None:
        return "unknown"
    if planning.status == "UNSUPPORTED":
        return "blocked"
    if planning.status == "REVIEW_REQUIRED":
        return "review_required"
    return "supported"


def _apply_order(artifacts: dict[str, str], *, deployment_status: str) -> list[dict[str, Any]]:
    if deployment_status != "supported":
        return []
    operations: list[dict[str, Any]] = []
    has_load_job = _first_artifact(artifacts, ".gcp.load_job.json") is not None
    for suffix, name, operation, command in (
        (".gcp.evidence_ddl.sql", "prepare_evidence", "QUERY", "bq query --use_legacy_sql=false"),
        (".gcp.load_job.json", "load_source", "LOAD", "bq load"),
        (".gcp.write.sql", "write_target", "QUERY", "bq query --use_legacy_sql=false"),
        (".gcp.schema_policy.json", "schema_evidence", "SCHEMA_EVIDENCE", "bq query --use_legacy_sql=false"),
        (".gcp.annotations.sql", "apply_annotations", "QUERY", "bq query --use_legacy_sql=false"),
        (".gcp.annotations_evidence.sql", "record_annotation_evidence", "QUERY", "bq query --use_legacy_sql=false"),
        (".gcp.policy_tags.json", "apply_policy_tags", "SCHEMA_UPDATE", "BigQuery tables.patch"),
        (".gcp.quality.sql", "quality", "QUERY", "bq query --use_legacy_sql=false"),
    ):
        if name == "write_target" and has_load_job:
            continue
        artifact = _first_artifact(artifacts, suffix)
        if artifact:
            operations.append(
                {
                    "name": name,
                    "operation": operation,
                    "artifact": artifact,
                    "apply_hint": command,
                }
            )
    return operations


def _review_boundaries(contract: SemanticContract) -> list[str]:
    boundaries = [
        "This manifest is deterministic and does not call Google Cloud APIs.",
        "Use contractforge-gcp smoke --execute for the validated single-contract BigQuery execution path.",
        "Project-level deployment orchestration remains a separate maturity track.",
    ]
    source_classification = classify_gcp_source(contract.source.raw)
    if source_classification.status == REVIEW_REQUIRED:
        boundaries.append(
            f"The declared source requires review before GCP execution: {source_classification.note}"
        )
    elif source_classification.status == UNSUPPORTED:
        boundaries.append(f"The declared source is not executable by the GCP adapter: {source_classification.note}")
    if contract.write.mode in {"scd1_hash_diff", "scd2_historical", "snapshot_soft_delete"}:
        boundaries.append("The declared write mode is outside the first stable GCP BigQuery surface.")
    boundaries.append(
        "Schema-policy artifacts include deterministic plans, and --enforce-schema-policy is the validated live runtime path for bounded schema enforcement."
    )
    boundaries.append("Automatic BigQuery type widening or mutation remains review-required outside the stable runtime path.")
    if contract.quality:
        boundaries.append(
            "Dataplex data-quality artifacts are deterministic review plans; native DataScan execution/readback is available through the explicit dataplex-quality command."
        )
    if has_dataplex_lineage_plan(contract):
        boundaries.append(
            "Dataplex lineage artifacts are deterministic native API plans; event publication/readback is available through the explicit dataplex-lineage-aspects command, not automatic deployment apply order."
        )
    if has_dataplex_aspect_plan(contract):
        boundaries.append(
            "Dataplex aspect artifacts are deterministic taxonomy/apply/readback plans; AspectType creation and modifyEntry execution are available through the explicit dataplex-lineage-aspects command, not automatic deployment apply order."
        )
    return boundaries


def _artifact_summary(artifacts: dict[str, str]) -> dict[str, Any]:
    deployment_artifacts = [
        {
            "name": name,
            "category": _category(name),
            "bytes": len(body.encode("utf-8")),
            "lines": len(body.splitlines()),
        }
        for name, body in sorted(artifacts.items())
    ]
    return {
        "artifact_count": len(deployment_artifacts),
        "total_bytes": sum(item["bytes"] for item in deployment_artifacts),
        "artifacts": deployment_artifacts,
    }


def _category(name: str) -> str:
    if name.endswith(".sql"):
        return "bigquery_sql"
    if name.endswith(".load_job.json"):
        return "bigquery_load_job"
    if name.endswith(".policy_tags.json"):
        return "governance"
    if name.endswith(".json"):
        return "metadata"
    if name.endswith(".md"):
        return "review"
    return "artifact"


def _first_artifact(artifacts: dict[str, str], suffix: str) -> str | None:
    for name in sorted(artifacts):
        if name.endswith(suffix):
            return name
    return None
