"""Optional model enrichment over deterministic ContractForge AI outputs."""

from contractforge_ai.enrichment.core import (
    EnrichmentResult,
    enrich_adapter_validation,
    enrich_control_table_analysis,
    enrich_failure_explanation,
    enrich_project_plan,
    enrich_project_spec,
    enrich_project_synthesis,
    enrich_review_result,
)

__all__ = [
    "EnrichmentResult",
    "enrich_adapter_validation",
    "enrich_control_table_analysis",
    "enrich_failure_explanation",
    "enrich_project_plan",
    "enrich_project_spec",
    "enrich_project_synthesis",
    "enrich_review_result",
]
