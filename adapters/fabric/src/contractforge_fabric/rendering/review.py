"""Render Fabric planning review artifacts."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.planner import ExecutionPlan, PlanningResult
from contractforge_core.semantic import SemanticContract
from contractforge_fabric.access import has_access_intent, render_access_plan
from contractforge_fabric.annotations import has_annotations, render_annotations_plan
from contractforge_fabric.capabilities import FABRIC_SUBTARGET_LAKEHOUSE, fabric_lakehouse_capabilities
from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.evidence import render_create_evidence_tables_sql
from contractforge_fabric.state import render_create_state_tables_sql
from contractforge_fabric.operations import has_operations_metadata, render_operations_json
from contractforge_fabric.preparation import can_render_preparation
from contractforge_fabric.contract_extensions import fabric_extensions
from contractforge_fabric.rendering.definition import render_notebook_item_definition
from contractforge_fabric.rendering.notebook import render_lakehouse_notebook
from contractforge_fabric.sources.object_storage import source_with_fabric_runtime_binding
from contractforge_fabric.sources import (
    is_fabric_source_renderable,
    list_fabric_source_support,
    render_fabric_source_review_json,
    render_fabric_source_review_markdown,
)

_PUBLIC_REVIEW_REQUIRED_SEMANTICS = {
    "scd2_historical": "historical",
    "snapshot_soft_delete": "snapshot_reconcile_soft_delete",
}


def render_fabric_review_artifacts(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    contract: SemanticContract | None = None,
    raw_contract: dict[str, Any] | None = None,
    environment: FabricEnvironment | None = None,
) -> RenderedArtifacts:
    env = environment or FabricEnvironment()
    prefix = _artifact_prefix(contract, plan)
    artifacts = {
        f"{prefix}.fabric.review.md": _planning_markdown(
            plan=plan,
            planning=planning,
            contract=contract,
            environment=env,
        ),
        f"{prefix}.fabric.capabilities.json": _capabilities_json(plan=plan, planning=planning, environment=env),
        f"{prefix}.fabric.source_support.json": json.dumps(list(list_fabric_source_support()), indent=2, sort_keys=True),
        f"{prefix}.fabric.runtime.todo.md": _runtime_todo(contract=contract, environment=env),
        f"{prefix}.fabric.evidence_ddl.sql": render_create_evidence_tables_sql(schema=env.evidence_schema or "contractforge"),
        f"{prefix}.fabric.state_ddl.sql": render_create_state_tables_sql(schema=env.evidence_schema or "contractforge"),
    }
    if raw_contract is not None:
        artifacts[f"{prefix}.fabric.contract.json"] = json.dumps(raw_contract, indent=2, sort_keys=True)
    effective_source = _effective_source(contract)
    if contract is not None:
        artifacts[f"{prefix}.fabric.source_review.json"] = render_fabric_source_review_json(effective_source)
        artifacts[f"{prefix}.fabric.source_review.md"] = render_fabric_source_review_markdown(effective_source)
    if contract is not None and has_annotations(contract):
        artifacts[f"{prefix}.fabric.annotations.json"] = render_annotations_plan(contract)
    if contract is not None and has_access_intent(contract):
        artifacts[f"{prefix}.fabric.access.json"] = render_access_plan(contract)
    if contract is not None and has_operations_metadata(contract):
        artifacts[f"{prefix}.fabric.operations.json"] = render_operations_json(contract)
    if contract is not None and is_fabric_source_renderable(effective_source) and can_render_preparation(contract):
        notebook = render_lakehouse_notebook(contract, env)
        artifacts[f"{prefix}.fabric.notebook.py"] = notebook
        artifacts[f"{prefix}.fabric.notebook.definition.json"] = render_notebook_item_definition(
            contract,
            env,
            notebook_source=notebook,
        )
    manifest_name = f"{prefix}.fabric.manifest.json"
    artifacts[manifest_name] = _manifest_json(
        plan=plan,
        planning=planning,
        artifacts=artifacts,
        manifest_name=manifest_name,
    )
    return RenderedArtifacts(artifacts=artifacts)


def _artifact_prefix(contract: SemanticContract | None, plan: ExecutionPlan | None) -> str:
    if contract is None:
        return (plan.platform if plan else FABRIC_SUBTARGET_LAKEHOUSE).replace(".", "_")
    namespace = (contract.target.namespace or "default").replace(".", "_")
    return f"{namespace}_{contract.target.name}"


def _effective_source(contract: SemanticContract | None) -> dict[str, Any]:
    if contract is None:
        return {}
    return source_with_fabric_runtime_binding(contract.source.raw or {}, fabric_extensions(contract))


def _capabilities_json(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    environment: FabricEnvironment,
) -> str:
    capabilities = fabric_lakehouse_capabilities()
    payload = {
        "adapter": "fabric",
        "subtarget": plan.platform if plan else FABRIC_SUBTARGET_LAKEHOUSE,
        "planning_status": planning.status if planning else None,
        "supports": {
            "append": capabilities.supports_append,
            "overwrite": capabilities.supports_overwrite,
            "upsert": capabilities.supports_merge,
            "hash_diff_upsert": capabilities.supports_hash_diff,
            "historical": capabilities.supports_scd2,
            "snapshot_reconcile_soft_delete": capabilities.supports_snapshot_soft_delete,
            "schema_evolution": capabilities.supports_schema_evolution,
            "row_filters": capabilities.supports_row_filters,
            "column_masks": capabilities.supports_column_masks,
            "available_now_streaming": capabilities.supports_available_now_streaming,
            "shape": capabilities.supports_shape,
            "transform": capabilities.supports_transform,
            "expression_quality": capabilities.supports_expression_quality,
        },
        "evidence": {
            "stores": list(capabilities.evidence_stores),
            "lakehouse": environment.evidence_lakehouse,
            "schema": environment.evidence_schema,
        },
        "runtime": {
            "status": "render_only",
            "workspace_id": environment.workspace_id,
            "workspace_name": environment.workspace_name,
            "tenant_id": environment.tenant_id,
            "tenant_domain": environment.tenant_domain,
            "lakehouse_id": environment.lakehouse_id,
            "lakehouse_name": environment.lakehouse_name,
            "warehouse_id": environment.warehouse_id,
            "warehouse_name": environment.warehouse_name,
            "artifact_uri": environment.artifact_uri,
            "notebook_id": environment.notebook_id,
            "notebook_name": environment.notebook_name,
            "pipeline_id": environment.pipeline_id,
        },
        "review_required_semantics": [
            _PUBLIC_REVIEW_REQUIRED_SEMANTICS.get(item, item) for item in capabilities.review_required_semantics
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _planning_markdown(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    contract: SemanticContract | None,
    environment: FabricEnvironment,
) -> str:
    lines = [
        "# Fabric Lakehouse Planning Review",
        "",
        "This artifact summarizes how a ContractForge contract maps to the Microsoft Fabric Lakehouse surface.",
        "Planning artifacts are review bundles. The explicit Fabric smoke workflow can deploy and submit generated notebooks, but full bronze-to-gold runtime parity and Data Factory updates are not validated yet.",
        "",
        "## Fabric Binding",
        "",
        f"- Workspace: `{environment.workspace_name or environment.workspace_id or 'UNSPECIFIED'}`",
        f"- Tenant: `{environment.tenant_domain or environment.tenant_id or 'UNSPECIFIED'}`",
        f"- Lakehouse: `{environment.lakehouse_name or environment.lakehouse_id or 'UNSPECIFIED'}`",
        f"- Warehouse: `{environment.warehouse_name or environment.warehouse_id or 'UNSPECIFIED'}`",
        f"- Evidence: `{_evidence_name(environment)}`",
        "",
    ]
    if contract:
        lines.extend(
            [
                "## Contract",
                "",
                f"- Source: `{contract.source.kind}`",
                f"- Target: `{contract.target.namespace or 'default'}.{contract.target.name}`",
                f"- Write mode: `{contract.write.mode}`",
                "",
            ]
        )
    if planning:
        lines.extend(["## Planning Result", "", f"- Status: `{planning.status}`", ""])
        if planning.blockers:
            lines.extend(["### Blockers", ""])
            lines.extend(f"- `{blocker.code}`: {blocker.message}" for blocker in planning.blockers)
            lines.append("")
        if planning.warnings:
            lines.extend(["### Warnings", ""])
            lines.extend(f"- `{warning.code}`: {warning.message}" for warning in planning.warnings)
            lines.append("")
    if plan:
        lines.extend(["## Abstract Plan", "", "| Step | Intent |", "| --- | --- |"])
        lines.extend(f"| `{step.name}` | {step.intent} |" for step in plan.steps)
        lines.append("")
    lines.extend(
        [
            "## Expected Fabric Mapping",
            "",
            "| ContractForge intent | Fabric target concept |",
            "| --- | --- |",
            "| Source read | OneLake Files/Tables, Lakehouse/Warehouse SQL endpoint, shortcut, Data Factory activity or notebook step |",
            "| Write target | Lakehouse Delta table or Warehouse table, depending on runtime design |",
            "| Transform | Notebook/Spark or SQL endpoint step |",
            "| Evidence | Lakehouse Delta evidence tables |",
            "| Deployment | Future Fabric REST/CLI/Data Factory pipeline integration |",
            "",
        ]
    )
    return "\n".join(lines)


def _runtime_todo(*, contract: SemanticContract | None, environment: FabricEnvironment) -> str:
    target = f"{contract.target.namespace or 'default'}.{contract.target.name}" if contract else "UNKNOWN"
    return "\n".join(
        [
            "# Fabric Runtime TODO",
            "",
            "This adapter version has planning artifacts plus a Notebook smoke workflow. To mature it, implement and validate:",
            "",
            "- Repeated real Fabric notebook execution without capacity throttling.",
            "- OneLake/Lakehouse table name resolution across bronze, silver and gold.",
            "- Data Factory pipeline artifact generation where connector-native orchestration is required.",
            "- Delta/Lakehouse evidence table DDL and writes.",
            "- Runtime insertion of run, quality, lineage and error evidence rows.",
            "- End-to-end bronze-to-gold contract execution without workaround code.",
            "",
            f"Target contract: `{target}`",
            f"Configured artifact URI: `{environment.artifact_uri or 'UNSPECIFIED'}`",
            "",
        ]
    )


def _manifest_json(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    artifacts: dict[str, str],
    manifest_name: str,
) -> str:
    payload = {
        "adapter": "fabric",
        "subtarget": plan.platform if plan else FABRIC_SUBTARGET_LAKEHOUSE,
        "planning_status": planning.status if planning else None,
        "artifact_summary": {
            "mode": "review_bundle",
            "execution_model": "render_only",
            "deployable": False,
            "count": len(artifacts) + 1,
            "bytes": sum(len(body.encode("utf-8")) for body in artifacts.values()),
        },
        "artifacts": sorted(tuple(artifacts) + (manifest_name,)),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _evidence_name(environment: FabricEnvironment) -> str:
    lakehouse = environment.evidence_lakehouse or environment.lakehouse_name or "CONTRACTFORGE_EVIDENCE_LH"
    schema = environment.evidence_schema or "contractforge"
    return f"{lakehouse}.{schema}"
