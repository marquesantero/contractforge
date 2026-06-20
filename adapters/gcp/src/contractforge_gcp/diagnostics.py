"""GCP planning diagnostics."""

from __future__ import annotations

from contractforge_core.planner import PlanningBlocker, PlanningWarning
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.sources import REVIEW_REQUIRED, UNSUPPORTED, classify_gcp_source


def unsupported_source_blockers(contract: SemanticContract) -> tuple[PlanningBlocker, ...]:
    classification = classify_gcp_source(contract.source.raw)
    if classification.status != UNSUPPORTED:
        return ()
    return (
        PlanningBlocker(
            code="GCP_UNSUPPORTED_SOURCE",
            message=f"GCP BigQuery adapter has no declared source mapping for `{classification.source_type}`.",
        ),
    )


def source_review_required(contract: SemanticContract) -> bool:
    return classify_gcp_source(contract.source.raw).status == REVIEW_REQUIRED


def gcp_planning_warnings(contract: SemanticContract) -> tuple[PlanningWarning, ...]:
    warnings: list[PlanningWarning] = [
        PlanningWarning(
            code="GCP_STABLE_SURFACE_SCOPE",
            message=(
                "GCP BigQuery is stable-final for the documented batch BigQuery surface. Streaming, advanced write "
                "modes, non-Workflows deployment runners, automatic native Dataplex lineage/aspect emission during every contract run, raw Iceberg paths, "
                "JDBC/Delta Sharing and live governance-ledger reconciliation are explicitly outside this scoped "
                "claim."
            ),
        )
    ]
    classification = classify_gcp_source(contract.source.raw)
    if classification.status == REVIEW_REQUIRED:
        warnings.append(
            PlanningWarning(
                code="GCP_SOURCE_REVIEW",
                message=f"`{classification.source_type}` maps to {classification.native_mapping}: {classification.note}",
            )
        )
    return tuple(warnings)
