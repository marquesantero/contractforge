"""Render AWS deployment manifest artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from contractforge_core.planner import ExecutionPlan, PlanningResult
from contractforge_core.semantic import SemanticContract
from contractforge_aws.rendering.manifest_boundaries import review_boundaries
from contractforge_aws.rendering.manifest_size import artifact_size_budget, artifact_summary
from contractforge_aws.rendering.names import artifact_prefix, iceberg_table_name


@dataclass(frozen=True)
class ArtifactDescriptor:
    name: str
    category: str
    applyable: bool
    requires_review: bool
    bytes: int
    lines: int
    order: int


def render_deployment_manifest(
    *,
    prefix: str,
    evidence_database: str,
    contract: SemanticContract | None,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    artifacts: dict[str, str],
) -> str:
    """Render a deterministic manifest over generated AWS artifacts."""

    manifest_name = f"{prefix}.deployment_manifest.json"
    payload = {
        "kind": "contractforge.aws.deployment_manifest.v1",
        "subtarget": "aws_glue_iceberg",
        "status": _status(planning=planning, artifacts=artifacts),
        "target": _target(contract),
        "evidence_database": evidence_database,
        "manifest_artifact": manifest_name,
        "artifact_summary": artifact_summary(artifacts),
        "artifact_size_budget": artifact_size_budget(artifacts),
        "artifacts": [descriptor.__dict__ for descriptor in _describe_artifacts(artifacts)],
        "abstract_steps": [step.name for step in plan.steps] if plan else [],
        "review_boundaries": review_boundaries(contract, artifacts),
        "optional_runtime_helpers": list(_OPTIONAL_RUNTIME_HELPERS),
        "optional_runtime_flow": _optional_runtime_flow(),
        "notes": [
            "Rendering does not call AWS APIs.",
            "Apply IAM, Lake Formation, networking, KMS and S3 bucket policies through reviewed infrastructure code.",
            "Generated Glue jobs persist supported ContractForge evidence tables in job; post-run reconciliation is explicit.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _status(*, planning: PlanningResult | None, artifacts: dict[str, str]) -> str:
    if f"{_common_prefix(artifacts)}.glue_job.py" in artifacts:
        return "renderable" if planning is None else str(planning.status).lower()
    return "review_required"


def _common_prefix(artifacts: dict[str, str]) -> str:
    first = next(iter(artifacts), "")
    return first.split(".", 1)[0]


def _target(contract: SemanticContract | None) -> dict[str, str]:
    if contract is None:
        return {"table": ""}
    return {
        "artifact_prefix": artifact_prefix(contract),
        "catalog_type": contract.target.catalog_type or "",
        "namespace": contract.target.namespace or "default",
        "name": contract.target.name,
        "table": iceberg_table_name(contract),
    }


def _describe_artifacts(artifacts: dict[str, str]) -> Iterable[ArtifactDescriptor]:
    names = sorted(artifacts, key=lambda name: (_order_group(name), name))
    for order, name in enumerate(names, start=1):
        body = artifacts[name]
        yield ArtifactDescriptor(
            name=name,
            category=_category(name),
            applyable=_applyable(name),
            requires_review=_requires_review(name),
            bytes=len(body.encode("utf-8")),
            lines=_line_count(body),
            order=order,
        )


def _line_count(body: str) -> int:
    return len(body.splitlines())


def _category(name: str) -> str:
    if _is_library_runner(name):
        return "runtime"
    for suffix, category in _CATEGORY_RULES:
        if name.endswith(suffix):
            return category
    return "review"


def _order_group(name: str) -> int:
    return _ORDER_GROUPS.get(_category(name), 90)


def _applyable(name: str) -> bool:
    return _is_library_runner(name) or any(name.endswith(suffix) for suffix in _APPLYABLE_SUFFIXES)


def _requires_review(name: str) -> bool:
    return not _is_library_runner(name)


def _is_library_runner(name: str) -> bool:
    return name == "runtime/contractforge_aws_runner.py"


def _optional_runtime_flow() -> list[dict[str, object]]:
    return [
        {
            "phase": phase,
            "helpers": list(helpers),
            "requires_aws_api": requires_aws_api,
        }
        for phase, helpers, requires_aws_api in _OPTIONAL_RUNTIME_FLOW
    ]


_OPTIONAL_RUNTIME_HELPERS = (
    "AthenaSqlRunner",
    "ensure_aws_evidence_tables",
    "audit_evidence_tables",
    "publish_aws_contract_artifacts_to_s3",
    "register_aws_glue_job",
    "register_aws_glue_job_definition_payload",
    "start_aws_glue_job_run",
    "get_aws_glue_job_run_status",
    "wait_aws_glue_job_run",
    "reconcile_aws_glue_job_run_evidence",
    "render_aws_glue_job_run_evidence_sql",
    "apply_aws_lake_formation_contract",
    "apply_aws_lake_formation_plan",
    "apply_aws_annotations_contract",
    "apply_aws_annotations_plan",
    "record_aws_operations_contract",
)

_OPTIONAL_RUNTIME_FLOW = (
    ("setup", ("AthenaSqlRunner", "ensure_aws_evidence_tables"), True),
    ("publish", ("publish_aws_contract_artifacts_to_s3",), True),
    ("register", ("register_aws_glue_job", "register_aws_glue_job_definition_payload"), True),
    ("run", ("start_aws_glue_job_run", "get_aws_glue_job_run_status", "wait_aws_glue_job_run"), True),
    ("governance", ("apply_aws_lake_formation_contract", "apply_aws_lake_formation_plan"), True),
    ("metadata", ("apply_aws_annotations_contract", "apply_aws_annotations_plan"), True),
    ("operations", ("record_aws_operations_contract",), False),
    ("post_run_evidence", ("reconcile_aws_glue_job_run_evidence", "render_aws_glue_job_run_evidence_sql"), True),
    ("audit", ("AthenaSqlRunner", "audit_evidence_tables"), True),
)

_CATEGORY_RULES = (
    (".glue_job.py", "runtime"),
    (".glue_job_definition.json", "deployment"),
    (".cloudformation.json", "deployment"),
    (".terraform.tf", "deployment"),
    (".iam_policy.json", "security"),
    (".lakeformation.json", "governance"),
    (".lakeformation_evidence.sql", "governance"),
    (".evidence.sql", "evidence"),
    (".evidence_ddl.sql", "evidence"),
    (".state_ddl.sql", "evidence"),
    (".cost.sql", "cost"),
    (".performance.sql", "performance"),
    (".performance_profile.json", "performance"),
    (".quality.dqdl", "quality"),
    (".annotations.json", "metadata"),
    (".annotations_evidence.sql", "metadata"),
    (".operations.json", "operations"),
    (".operations.sql", "operations"),
    (".native_passthrough.json", "native_passthrough"),
)

_APPLYABLE_SUFFIXES = (
    ".glue_job_definition.json",
    ".cloudformation.json",
    ".terraform.tf",
    ".evidence_ddl.sql",
    ".state_ddl.sql",
)

_ORDER_GROUPS = {
    "review": 10,
    "security": 20,
    "governance": 30,
    "metadata": 40,
    "operations": 45,
    "evidence": 50,
    "quality": 55,
    "performance": 58,
    "runtime": 60,
    "deployment": 70,
    "native_passthrough": 80,
    "cost": 85,
}
