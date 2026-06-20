"""Generate missing sibling governance contracts for existing ingestion contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from contractforge_ai.agentic.context import analyze_project_state
from contractforge_ai.agentic.models import ContractSummary
from contractforge_ai.models import RequiredDecision
from contractforge_ai.projects.models import DecisionReport, ProjectArtifact, ProjectPlan
from contractforge_ai.projects.patching import ProjectPatchPlan, plan_project_patches


@dataclass(frozen=True)
class MissingSiblingContractPlan:
    """Generated sibling contracts plus the patch plan for review."""

    artifacts: list[ProjectArtifact] = field(default_factory=list)
    patch_plan: ProjectPatchPlan | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "patch_plan": self.patch_plan.to_dict() if self.patch_plan else None,
        }


def generate_missing_sibling_contracts(
    project_root: str | Path,
    *,
    include_annotations: bool = True,
    include_operations: bool = True,
    allow_updates: bool = False,
) -> MissingSiblingContractPlan:
    """Generate missing annotations/operations sibling contracts for existing ingestion contracts.

    The generated files are intentionally conservative. They provide the valid split-contract
    structure and mark ownership, SLA and descriptive metadata fields for human review instead of
    inventing operational accountability.
    """

    state = analyze_project_state(project_root)
    artifacts: list[ProjectArtifact] = []
    for contract in state.contracts:
        if include_annotations and not contract.has_annotations:
            artifacts.append(_annotations_artifact(contract))
        if include_operations and not contract.has_operations:
            artifacts.append(_operations_artifact(contract))

    patch_plan = plan_project_patches(
        ProjectPlan(
            name="missing_sibling_contracts",
            target="contractforge-sibling-contracts",
            artifacts=artifacts,
            report=_decision_report(artifacts),
        ),
        project_root,
        allow_updates=allow_updates,
    )
    return MissingSiblingContractPlan(artifacts=artifacts, patch_plan=patch_plan)


def _annotations_artifact(contract: ContractSummary) -> ProjectArtifact:
    payload = {
        "table": {
            "description": f"Review and describe {contract.full_target_name or contract.target_table or 'this table'}.",
            "aliases": [],
            "tags": {
                "layer": contract.layer or "review_required",
                "contractforge.generated": "true",
                "review_required": "true",
            },
        },
        "columns": {},
    }
    return ProjectArtifact(
        path=contract.path.replace(".ingestion.yaml", ".annotations.yaml"),
        kind="annotation",
        description="Draft annotations sibling contract generated from an existing ingestion contract.",
        content=yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
    )


def _operations_artifact(contract: ContractSummary) -> ProjectArtifact:
    payload = {
        "operations": {
            "business_owner": "REVIEW_REQUIRED",
            "technical_owner": "REVIEW_REQUIRED",
            "steward": "REVIEW_REQUIRED",
            "support_group": "REVIEW_REQUIRED",
            "escalation_group": "REVIEW_REQUIRED",
            "criticality": "medium",
            "expected_frequency": "review_required",
            "freshness_sla_minutes": None,
            "alert_on_failure": True,
            "alert_on_quality_fail": True,
            "runbook_url": "REVIEW_REQUIRED",
            "tags": {
                "layer": contract.layer or "review_required",
                "contractforge.generated": "true",
                "review_required": "true",
            },
        }
    }
    return ProjectArtifact(
        path=contract.path.replace(".ingestion.yaml", ".operations.yaml"),
        kind="operation",
        description="Draft operations sibling contract generated from an existing ingestion contract.",
        content=yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
    )


def _decision_report(artifacts: list[ProjectArtifact]) -> DecisionReport:
    if not artifacts:
        return DecisionReport(
            title="Missing Sibling Contracts",
            summary="No missing annotations or operations sibling contracts were found.",
        )
    return DecisionReport(
        title="Missing Sibling Contracts",
        summary=f"Drafted {len(artifacts)} missing sibling governance contract(s) for review.",
        decisions_required=[
            RequiredDecision(
                question="Confirm table and column descriptions before applying annotations.",
                reason="Generated annotations provide structure only; business descriptions must be reviewed.",
                path="annotations.table.description",
            ),
            RequiredDecision(
                question="Confirm ownership, support groups, SLA and runbook before applying operations.",
                reason="Operational accountability should not be inferred from an ingestion contract alone.",
                path="operations",
            ),
        ],
    )
