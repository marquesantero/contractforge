"""Build abstract execution plans from semantic contracts."""

from __future__ import annotations

from contractforge_core.capabilities.models import PlatformCapabilities
from contractforge_core.planner.result import ExecutionPlan, ExecutionStep
from contractforge_core.semantic.models import SemanticContract


def build_execution_plan(contract: SemanticContract, capabilities: PlatformCapabilities) -> ExecutionPlan:
    steps = [ExecutionStep("read_source", f"Read {contract.source.kind} source intent.")]
    if contract.shape:
        steps.append(ExecutionStep("shape", "Apply structural shape intent."))
    if contract.transform:
        steps.append(ExecutionStep("transform", "Apply transform intent."))
    if contract.quality:
        steps.append(ExecutionStep("quality", "Evaluate quality intent."))
    steps.extend(
        [
            ExecutionStep("write_target", f"Apply {contract.write.mode} write intent."),
            ExecutionStep("record_evidence", "Record run, quality, schema, and lineage evidence."),
        ]
    )
    evidence_required = (
        True
        if contract.operations is None
        else contract.operations.require_production_evidence
    )
    return ExecutionPlan(platform=capabilities.platform, steps=tuple(steps), evidence_required=evidence_required)
