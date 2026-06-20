"""Intent-first project generation orchestration."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

import yaml

from contractforge_ai.agentic.context import analyze_project_state
from contractforge_ai.agentic.governance import (
    ContextSnapshot,
    GenerationAuditTrail,
    GenerationPolicyEngine,
    GenerationPolicyResult,
    GenerationSignature,
    ProviderProposalAudit,
    ProviderProposalDecision,
)
from contractforge_ai.agentic.intent import interpret_intent
from contractforge_ai.agentic.models import GapPlan, IntentSpec, ProjectState, TransformationPlan, TransformationStep
from contractforge_ai.agentic.planning import plan_project_gaps
from contractforge_ai.agentic.transform import infer_transformation_plan
from contractforge_ai.enrichment import EnrichmentResult, enrich_project_plan, enrich_project_spec
from contractforge_ai.generators.environments import aws_glue_iceberg_environment_payload, databricks_environment_payload
from contractforge_ai.generators.project import generate_contractforge_yaml_project
from contractforge_ai.models import Assumption, EvidenceItem, RequiredDecision, Traceability
from contractforge_ai.projects.artifact_policy import split_human_review_artifacts
from contractforge_ai.projects.models import DecisionReport, ProjectArtifact, ProjectPlan
from contractforge_ai.providers import ModelProvider
from contractforge_ai.reports import render_intent_generation_review, render_markdown_report
from contractforge_ai.reports_translation import translate_report
from contractforge_ai.validation import validate_project_plan_artifact
from contractforge_ai.write_modes import canonical_write_mode

_TRANSFORMATION_PROVIDER_FIELDS = frozenset({"shape_columns", "transform.shape.columns", "shape", "transform"})


class SparkLike(Protocol):
    """Minimal Spark protocol for table schema inspection."""

    def table(self, table_name: str) -> Any:
        """Return a Spark DataFrame-like object."""


@dataclass(frozen=True)
class AdapterEnvironmentTemplate:
    """Environment artifact template for adapters with generated project support."""

    path: str
    description: str
    payload: dict[str, Any]


_ADAPTER_ENVIRONMENT_TEMPLATES: dict[str, AdapterEnvironmentTemplate] = {
    "aws": AdapterEnvironmentTemplate(
        path="environments/aws.environment.yaml",
        description="AWS environment contract scaffold. Fill deployment/runtime values before deploy.",
        payload=aws_glue_iceberg_environment_payload("intent-project", evidence_database="ops"),
    ),
    "databricks": AdapterEnvironmentTemplate(
        path="environments/databricks.environment.yaml",
        description="Databricks environment contract scaffold. Fill runtime/deployment values before deploy.",
        payload=databricks_environment_payload(),
    ),
}


@dataclass(frozen=True)
class IntentGenerationRequest:
    """Free-form generation request for a ContractForge project."""

    prompt: str
    schema_path: str | None = None
    schema_paths: tuple[str, ...] = ()
    sample_table: str | None = None
    project_root: str | None = None
    output_target: str = "contractforge-yaml"
    default_catalog: str | None = None
    allow_review_required: bool = True
    language: str = "en"
    provider: ModelProvider | None = None
    spark: SparkLike | None = None


@dataclass(frozen=True)
class IntentGenerationResult:
    """Result of an intent-first project generation workflow."""

    status: str
    project: ProjectPlan | None
    layers: list[str]
    schema_source: dict[str, Any]
    intent: IntentSpec | None = None
    project_state: ProjectState | None = None
    gap_plan: GapPlan | None = None
    transformation_plan: TransformationPlan | None = None
    context_snapshot: ContextSnapshot | None = None
    generation_signature: GenerationSignature | None = None
    policy_result: GenerationPolicyResult | None = None
    audit_trail: GenerationAuditTrail | None = None
    provider_proposal_audit: ProviderProposalAudit | None = None
    transformation_enrichment: EnrichmentResult | None = None
    pre_generation_enrichment: EnrichmentResult | None = None
    enrichment: EnrichmentResult | None = None

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return {
            "status": self.status,
            "layers": self.layers,
            "schema_source": self.schema_source,
            "intent": self.intent.to_dict() if self.intent else None,
            "project_state": self.project_state.to_dict() if self.project_state else None,
            "gap_plan": self.gap_plan.to_dict() if self.gap_plan else None,
            "transformation_plan": self.transformation_plan.to_dict() if self.transformation_plan else None,
            "context_snapshot": self.context_snapshot.to_dict() if self.context_snapshot else None,
            "generation_signature": self.generation_signature.to_dict() if self.generation_signature else None,
            "policy_result": self.policy_result.to_dict() if self.policy_result else None,
            "audit_trail": self.audit_trail.to_dict() if self.audit_trail else None,
            "provider_proposal_audit": self.provider_proposal_audit.to_dict() if self.provider_proposal_audit else None,
            "transformation_enrichment": self.transformation_enrichment.to_dict() if self.transformation_enrichment else None,
            "pre_generation_enrichment": self.pre_generation_enrichment.to_dict() if self.pre_generation_enrichment else None,
            "project": self.project.to_dict(include_content=include_content) if self.project else None,
            "enrichment": self.enrichment.to_dict() if self.enrichment else None,
        }


def generate_from_intent(request: IntentGenerationRequest) -> IntentGenerationResult:
    """Generate a ContractForge project from a free-form user request."""

    if not request.prompt.strip():
        raise ValueError("Generation prompt cannot be empty.")

    audit = GenerationAuditTrail()
    intent = interpret_intent(
        request.prompt,
        sample_table=request.sample_table,
        default_catalog=request.default_catalog,
        output_target=request.output_target,
    )
    audit.record("intent_normalization", "resolved", requested_layers=intent.requested_layers, base_name=intent.base_name)
    project_state = analyze_project_state(request.project_root)
    audit.record("context_analysis", "resolved", project_root=request.project_root, existing_layers=project_state.layers)
    intent = _apply_project_state_defaults(intent, project_state)
    gap_plan = plan_project_gaps(intent, project_state)
    audit.record("gap_planning", "resolved", layers_to_generate=gap_plan.layers_to_generate)

    schema_paths = _request_schema_paths(request)
    if len(schema_paths) > 1:
        schema_source = {"kind": "schema_paths", "paths": list(schema_paths), "count": len(schema_paths)}
        transformation_plan = TransformationPlan()
        audit.record("transformation_planning", "resolved", shape_columns=[], schema_count=len(schema_paths))
        context_snapshot = ContextSnapshot(project_state=project_state, schema_source=schema_source)
        signature = GenerationSignature(
            intent=intent,
            context_snapshot=context_snapshot,
            gap_plan=gap_plan,
            transformation_plan=transformation_plan,
        )
        policy_result = GenerationPolicyEngine().evaluate(signature)
        audit.record("policy_evaluation", policy_result.action, findings=[finding.code for finding in policy_result.findings])
        if not schema_paths:
            return _missing_schema_result(
                request,
                schema_source,
                intent=intent,
                project_state=project_state,
                gap_plan=gap_plan,
                transformation_plan=transformation_plan,
                context_snapshot=context_snapshot,
                generation_signature=signature,
                policy_result=policy_result,
                audit_trail=audit,
                provider_proposal_audit=None,
                transformation_enrichment=None,
                pre_generation_enrichment=None,
            )
        project = _generate_multi_schema_medallion_project(
            request,
            schema_paths=schema_paths,
            intent=intent,
            gap_plan=gap_plan,
        )
        enrichment = _enrich_project(project, request)
        project = _attach_review_html(
            project,
            request=request,
            schema_source=schema_source,
            provider_proposal_audit=None,
            transformation_enrichment=None,
            pre_generation_enrichment=None,
            enrichment=enrichment,
            intent=intent,
            project_state=project_state,
            gap_plan=gap_plan,
            transformation_plan=transformation_plan,
            context_snapshot=context_snapshot,
            generation_signature=signature,
            policy_result=policy_result,
            audit_trail=audit,
        )
        validation = validate_project_plan_artifact(project, use_contractforge=False)
        status = "READY" if validation.ready else validation.status
        return IntentGenerationResult(
            status=status,
            project=project,
            layers=gap_plan.layers_to_generate,
            schema_source=schema_source,
            intent=intent,
            project_state=project_state,
            gap_plan=gap_plan,
            transformation_plan=transformation_plan,
            context_snapshot=context_snapshot,
            generation_signature=signature,
            policy_result=policy_result,
            audit_trail=audit,
            enrichment=enrichment,
        )

    schema_path, schema_source = _resolve_schema_path(request)
    transformation_plan = infer_transformation_plan(intent, schema_path=schema_path)
    audit.record("transformation_planning", "resolved", shape_columns=list(transformation_plan.shape_columns))
    transformation_plan, transformation_enrichment, provider_proposal_audit = _refine_transformation_plan(
        request,
        intent=intent,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
        schema_path=schema_path,
    )
    if transformation_enrichment is not None:
        audit.record(
            "provider_transformation_refinement",
            transformation_enrichment.status.lower(),
            provider=transformation_enrichment.provider,
            prompt=transformation_enrichment.prompt,
            applied_shape_columns=list(transformation_plan.shape_columns),
            proposal_audit=provider_proposal_audit.to_dict() if provider_proposal_audit else None,
        )
    context_snapshot = ContextSnapshot(project_state=project_state, schema_source=schema_source)
    signature = GenerationSignature(
        intent=intent,
        context_snapshot=context_snapshot,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
    )
    policy_result = GenerationPolicyEngine().evaluate(signature)
    audit.record("policy_evaluation", policy_result.action, findings=[finding.code for finding in policy_result.findings])
    pre_generation_enrichment = _enrich_generation_plan(
        request,
        intent=intent,
        project_state=project_state,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
        context_snapshot=context_snapshot,
        generation_signature=signature,
        policy_result=policy_result,
    )
    if pre_generation_enrichment is not None:
        audit.record(
            "provider_pre_generation",
            pre_generation_enrichment.status.lower(),
            provider=pre_generation_enrichment.provider,
            prompt=pre_generation_enrichment.prompt,
            recommendations=len((pre_generation_enrichment.data or {}).get("recommendations", [])),
            decisions=len((pre_generation_enrichment.data or {}).get("decisions_required", [])),
        )
    if not schema_path:
        return _missing_schema_result(
            request,
            schema_source,
            intent=intent,
            project_state=project_state,
            gap_plan=gap_plan,
            transformation_plan=transformation_plan,
            context_snapshot=context_snapshot,
            generation_signature=signature,
            policy_result=policy_result,
            audit_trail=audit,
            provider_proposal_audit=provider_proposal_audit,
            transformation_enrichment=transformation_enrichment,
            pre_generation_enrichment=pre_generation_enrichment,
        )

    layers = gap_plan.layers_to_generate

    if not layers:
        project = _no_generation_project(
            request,
            intent=intent,
            project_state=project_state,
            gap_plan=gap_plan,
            transformation_plan=transformation_plan,
        )
    else:
        project = _generate_medallion_project(
            request,
            schema_path=schema_path,
            intent=intent,
            gap_plan=gap_plan,
            transformation_plan=transformation_plan,
        )
    enrichment = _enrich_project(project, request)
    project = _attach_review_html(
        project,
        request=request,
        schema_source=schema_source,
        provider_proposal_audit=provider_proposal_audit,
        transformation_enrichment=transformation_enrichment,
        pre_generation_enrichment=pre_generation_enrichment,
        enrichment=enrichment,
        intent=intent,
        project_state=project_state,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
        context_snapshot=context_snapshot,
        generation_signature=signature,
        policy_result=policy_result,
        audit_trail=audit,
    )
    validation = validate_project_plan_artifact(project, use_contractforge=False)
    status = "READY" if validation.ready else validation.status
    return IntentGenerationResult(
        status=status,
        project=project,
        layers=layers,
        schema_source=schema_source,
        intent=intent,
        project_state=project_state,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
        context_snapshot=context_snapshot,
        generation_signature=signature,
        policy_result=policy_result,
        audit_trail=audit,
        provider_proposal_audit=provider_proposal_audit,
        transformation_enrichment=transformation_enrichment,
        pre_generation_enrichment=pre_generation_enrichment,
        enrichment=enrichment,
    )


def _apply_project_state_defaults(intent: IntentSpec, project_state: ProjectState) -> IntentSpec:
    if not project_state.contracts:
        return intent
    updates: dict[str, Any] = {}
    if intent.base_name == "generated_project":
        for contract in project_state.contracts:
            if contract.target_table:
                updates["base_name"] = _safe_name(
                    contract.target_table.removeprefix("b_").removeprefix("s_").removeprefix("g_")
                )
                break
    if intent.catalog == "main":
        for contract in project_state.contracts:
            if contract.target_catalog:
                updates["catalog"] = contract.target_catalog
                break
    return replace(intent, **updates) if updates else intent


def _missing_schema_result(
    request: IntentGenerationRequest,
    schema_source: dict[str, Any],
    *,
    intent: IntentSpec,
    project_state: ProjectState,
    gap_plan: GapPlan,
    transformation_plan: TransformationPlan,
    context_snapshot: ContextSnapshot,
    generation_signature: GenerationSignature,
    policy_result: GenerationPolicyResult,
    audit_trail: GenerationAuditTrail,
    provider_proposal_audit: ProviderProposalAudit | None,
    transformation_enrichment: EnrichmentResult | None,
    pre_generation_enrichment: EnrichmentResult | None,
) -> IntentGenerationResult:
    missing_schema_report = translate_report(
        render_markdown_report(
            _missing_schema_markdown(request, schema_source),
            title="ContractForge AI Generation Review",
        ),
        language=request.language,
        provider=request.provider,
    )
    project = ProjectPlan(
        name=_safe_name(intent.base_name),
        target="intent-first",
        artifacts=[
            ProjectArtifact(
                path="AI_REVIEW.html",
                kind="other",
                description="Rich review explaining why generation needs more evidence.",
                content=missing_schema_report.html,
            )
        ],
        report=DecisionReport(
            title="Intent-first generation needs schema evidence",
            summary="A schema path or inspectable sample table is required before generating contracts.",
            decisions_required=[
                RequiredDecision(
                    question="Provide a schema/profile path or an inspectable sample table.",
                    reason="ContractForge AI will not invent source columns for production project generation.",
                    path="schema_path",
                ),
                *transformation_plan.decisions_required,
            ],
        ),
        traceability=Traceability(
            confidence=0.25,
            evidence=[
                EvidenceItem(
                    source="user_prompt",
                    reason="User requested project generation but no schema evidence was available.",
                    value={"sample_table": request.sample_table},
                    confidence=0.25,
                )
            ],
            review_required=True,
        ),
    )
    return IntentGenerationResult(
        status="NEEDS_DECISIONS",
        project=project,
        layers=[],
        schema_source=schema_source,
        intent=intent,
        project_state=project_state,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
        context_snapshot=context_snapshot,
        generation_signature=generation_signature,
        policy_result=policy_result,
        audit_trail=audit_trail,
        provider_proposal_audit=provider_proposal_audit,
        transformation_enrichment=transformation_enrichment,
        pre_generation_enrichment=pre_generation_enrichment,
    )


def _generate_medallion_project(
    request: IntentGenerationRequest,
    *,
    schema_path: str,
    intent: IntentSpec,
    gap_plan: GapPlan,
    transformation_plan: TransformationPlan,
) -> ProjectPlan:
    all_artifacts: list[ProjectArtifact] = []
    assumptions: list[Assumption] = []
    decisions: list[RequiredDecision] = [*intent.decisions_required, *gap_plan.decisions_required, *transformation_plan.decisions_required]
    warnings: list[str] = [*gap_plan.warnings, *transformation_plan.warnings]
    project_steps: list[dict[str, Any]] = []
    project_connections: dict[str, str] = {}
    previous_step: str | None = None

    for action in gap_plan.actions:
        if action.action != "generate":
            continue
        layer = action.layer
        target_schema = layer
        target_table = _layer_table(layer, intent.base_name)
        step_name = f"{layer}_{target_table}"
        connection_name = f"{layer}_source"
        contract_path = f"contracts/{layer}/{target_table}.ingestion.yaml"
        source_path = action.source_table or (intent.source or "REVIEW_REQUIRED")
        mode = _mode_for_layer(layer, intent.silver_mode)
        connector = _connector_for_source(source_path)
        layer_plan = generate_contractforge_yaml_project(
            schema_path,
            project_name=f"{intent.base_name.title()} {layer.title()}",
            connector=connector,
            source_path=source_path,
            target_catalog=intent.catalog,
            target_schema=target_schema,
            target_table=target_table,
            layer=layer,
            mode=mode,
            include_project_artifacts=False,
            connection_name=connection_name,
        )
        project_connections[connection_name] = f"connections/{connection_name}.yaml"
        project_steps.append(
            {
                "name": step_name,
                "layer": layer,
                "depends_on": [previous_step] if previous_step else [],
                "contracts": _intent_contract_entries(intent, contract_path),
            }
        )
        previous_step = step_name
        layer_artifacts = [
            _rewrite_layer_artifact(
                artifact,
                layer=layer,
                intent=intent,
                transformation_plan=transformation_plan,
            )
            for artifact in layer_plan.artifacts
        ]
        split = split_human_review_artifacts(layer_artifacts, extra_paths={"README.md"})
        all_artifacts.extend(split.kept)
        assumptions.extend(layer_plan.report.assumptions)
        decisions.extend(layer_plan.report.decisions_required)
        warnings.extend(layer_plan.report.warnings)

    all_artifacts = [
        _intent_project_yaml(intent=intent, connections=project_connections, steps=project_steps),
        _intent_review_environment_yaml(),
        *_intent_adapter_environment_yamls(intent),
        *all_artifacts,
    ]

    report = DecisionReport(
        title=f"{intent.base_name.title()} Intent-First Project",
        summary=f"Generated {', '.join(gap_plan.layers_to_generate)} ContractForge contracts from a context-aware intent plan.",
        assumptions=assumptions,
        decisions_required=decisions,
        warnings=warnings,
    )
    return ProjectPlan(
        name=_safe_name(f"{intent.base_name}_intent_project"),
        target="intent-first-medallion",
        artifacts=all_artifacts,
        report=report,
        traceability=Traceability(
            confidence=0.70,
            evidence=[
                EvidenceItem(
                    source="intent_first_generation",
                    reason="Generated ContractForge contracts from an interpreted intent and gap plan.",
                    value={"layers": gap_plan.layers_to_generate, "base_name": intent.base_name, "final_columns": intent.final_columns},
                    confidence=0.70,
                )
            ],
            assumptions=assumptions,
            decisions_required=decisions,
            review_required=True,
        ),
    )


def _generate_multi_schema_medallion_project(
    request: IntentGenerationRequest,
    *,
    schema_paths: tuple[str, ...],
    intent: IntentSpec,
    gap_plan: GapPlan,
) -> ProjectPlan:
    all_artifacts: list[ProjectArtifact] = []
    assumptions: list[Assumption] = []
    decisions: list[RequiredDecision] = [*intent.decisions_required, *gap_plan.decisions_required]
    warnings: list[str] = [*gap_plan.warnings]
    project_steps: list[dict[str, Any]] = []
    project_connections: dict[str, str] = {}
    layers = intent.requested_layers if intent.requested_layers else ["bronze"]

    for schema_path in schema_paths:
        dataset = _dataset_name_from_schema(schema_path)
        previous_step: str | None = None
        source_root = intent.source or "REVIEW_REQUIRED"
        for layer in layers:
            target_table = _layer_table(layer, dataset)
            step_name = f"{dataset}_{layer}_{target_table}"
            connection_name = f"{dataset}_{layer}_source"
            contract_path = f"contracts/{layer}/{target_table}.ingestion.yaml"
            source_path = _multi_schema_source_path(source_root, dataset, layer=layer, catalog=intent.catalog)
            mode = _multi_schema_mode(request.prompt, dataset=dataset, layer=layer, intent=intent)
            connector = _multi_schema_connector(request.prompt, dataset=dataset, source_path=source_path)
            layer_plan = generate_contractforge_yaml_project(
                schema_path,
                project_name=f"{dataset.title()} {layer.title()}",
                connector=connector,
                source_path=source_path,
                target_catalog=intent.catalog,
                target_schema=layer,
                target_table=target_table,
                layer=layer,
                mode=mode,
                include_project_artifacts=False,
                connection_name=connection_name,
            )
            project_connections[connection_name] = f"connections/{connection_name}.yaml"
            project_steps.append(
                {
                    "name": step_name,
                    "layer": layer,
                    "dataset": dataset,
                    "depends_on": [previous_step] if previous_step else [],
                    "contracts": _intent_contract_entries(intent, contract_path),
                }
            )
            previous_step = step_name
            layer_artifacts = [
                _rewrite_layer_artifact(
                    artifact,
                    layer=layer,
                    intent=intent,
                    transformation_plan=infer_transformation_plan(intent, schema_path=schema_path),
                )
                for artifact in layer_plan.artifacts
            ]
            split = split_human_review_artifacts(layer_artifacts, extra_paths={"README.md"})
            all_artifacts.extend(split.kept)
            assumptions.extend(layer_plan.report.assumptions)
            decisions.extend(layer_plan.report.decisions_required)
            warnings.extend(layer_plan.report.warnings)

    project_name = _safe_name(f"{intent.base_name}_multi_schema_project")
    all_artifacts = [
        _intent_project_yaml(intent=intent, connections=project_connections, steps=project_steps, project_name=project_name),
        _intent_review_environment_yaml(),
        *_intent_adapter_environment_yamls(intent),
        *all_artifacts,
    ]

    return ProjectPlan(
        name=project_name,
        target="intent-first-medallion",
        artifacts=all_artifacts,
        report=DecisionReport(
            title=f"{intent.base_name.title()} Multi-Schema Intent Project",
            summary=f"Generated {len(schema_paths)} dataset flow(s) in one ContractForge project.",
            assumptions=assumptions,
            decisions_required=decisions,
            warnings=warnings,
        ),
        traceability=Traceability(
            confidence=0.70,
            evidence=[
                EvidenceItem(
                    source="intent_first_multi_schema_generation",
                    reason="Generated one medallion chain per schema path from a shared user prompt.",
                    value={"schemas": list(schema_paths), "layers": layers},
                    confidence=0.70,
                )
            ],
            assumptions=assumptions,
            decisions_required=decisions,
            review_required=True,
        ),
    )


def _no_generation_project(
    request: IntentGenerationRequest,
    *,
    intent: IntentSpec,
    project_state: ProjectState,
    gap_plan: GapPlan,
    transformation_plan: TransformationPlan,
    context_snapshot: ContextSnapshot,
    generation_signature: GenerationSignature,
    policy_result: GenerationPolicyResult,
    audit_trail: GenerationAuditTrail,
) -> ProjectPlan:
    return ProjectPlan(
        name=_safe_name(f"{intent.base_name}_review"),
        target="intent-first-review",
        artifacts=[],
        report=DecisionReport(
            title=f"{intent.base_name.title()} Project Review",
            summary="The requested project state already exists or no generation action was required.",
            decisions_required=[*intent.decisions_required, *gap_plan.decisions_required, *transformation_plan.decisions_required],
            warnings=[*project_state.warnings, *gap_plan.warnings, *transformation_plan.warnings],
        ),
        traceability=Traceability(
            confidence=0.78,
            evidence=[
                EvidenceItem(
                    source="project_state",
                    reason="Existing project context was analyzed before deciding that no new contract artifacts were needed.",
                    value={"layers": project_state.layers, "actions": [action.to_dict() for action in gap_plan.actions]},
                    confidence=0.78,
                )
            ],
            review_required=True,
        ),
    )


def _rewrite_layer_artifact(
    artifact: ProjectArtifact,
    *,
    layer: str,
    intent: IntentSpec,
    transformation_plan: TransformationPlan,
) -> ProjectArtifact:
    if artifact.path.endswith(".operations.yaml") and intent.operations:
        return _update_yaml_artifact(
            artifact,
            lambda payload: _deep_merge(payload, intent.operations),
        )
    if not artifact.path.endswith(".ingestion.yaml"):
        return artifact
    try:
        payload = yaml.safe_load(artifact.content)
    except Exception:
        return artifact
    if not isinstance(payload, dict):
        return artifact
    if payload.get("source", {}).get("connector") == "table":
        source = dict(payload["source"])
        source["table"] = source.pop("path")
        payload["source"] = source
    if intent.quality_rules:
        payload["quality_rules"] = _deep_merge(_mapping(payload.get("quality_rules")), intent.quality_rules)
    if canonical_write_mode(str(payload.get("mode") or "")) == "scd1_hash_diff" and intent.hash_columns:
        payload["hash_keys"] = intent.hash_columns
    contract_transform = transformation_plan.contract_transform
    if layer == "gold" and contract_transform:
        payload.setdefault("transform", {})
        payload["transform"] = _deep_merge(payload["transform"], contract_transform)
    return ProjectArtifact(
        path=artifact.path,
        kind=artifact.kind,
        description=artifact.description,
        executable=artifact.executable,
        content=yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
    )


def _intent_project_yaml(
    *,
    intent: IntentSpec,
    connections: dict[str, str],
    steps: list[dict[str, Any]],
    project_name: str | None = None,
) -> ProjectArtifact:
    payload = {
        "name": project_name or _safe_name(f"{intent.base_name}_intent_project"),
        "description": "Intent-first ContractForge medallion project generated by ContractForge AI.",
        "environments": _intent_environment_entries(intent),
        "connections": connections,
        "schedule": _intent_schedule(intent),
        "execution_order": steps,
    }
    return ProjectArtifact(
        path="project.yaml",
        kind="config",
        description="Aggregate ContractForge project metadata for the generated medallion flow.",
        content=yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
    )


def _intent_schedule(intent: IntentSpec) -> dict[str, Any]:
    schedule = {
        "cron": "0 6 * * *",
        "timezone": "UTC",
        "enabled": False,
    }
    schedule.update(intent.schedule)
    return schedule


def _intent_environment_entries(intent: IntentSpec) -> dict[str, str]:
    entries = {"review": "environments/review.environment.yaml"}
    for key in _supported_adapter_environment_keys(intent):
        entries[key] = _ADAPTER_ENVIRONMENT_TEMPLATES[key].path
    return entries


def _intent_contract_entries(intent: IntentSpec, contract_path: str) -> dict[str, str]:
    entries = {"review": contract_path}
    for key in _supported_adapter_environment_keys(intent):
        entries[key] = contract_path
    return entries


def _intent_adapter_environment_yamls(intent: IntentSpec) -> list[ProjectArtifact]:
    return [
        _intent_adapter_environment_yaml(template)
        for template in _supported_adapter_environment_templates(intent)
    ]


def _intent_adapter_environment_yaml(template: AdapterEnvironmentTemplate) -> ProjectArtifact:
    payload = _deep_merge({}, template.payload)
    return ProjectArtifact(
        path=template.path,
        kind="config",
        description=template.description,
        content=yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
    )


def _supported_adapter_environment_templates(intent: IntentSpec) -> list[AdapterEnvironmentTemplate]:
    return [
        _ADAPTER_ENVIRONMENT_TEMPLATES[key]
        for key in _supported_adapter_environment_keys(intent)
    ]


def _supported_adapter_environment_keys(intent: IntentSpec) -> list[str]:
    return [
        key
        for key in intent.platform_hints
        if key in _ADAPTER_ENVIRONMENT_TEMPLATES
    ]


def _intent_review_environment_yaml() -> ProjectArtifact:
    return ProjectArtifact(
        path="environments/review.environment.yaml",
        kind="config",
        description="Review environment contract. Choose the real adapter before deployment.",
        content=yaml.safe_dump(
            {
                "name": "review",
                "adapter": "REVIEW_REQUIRED",
                "evidence": {
                    "schema": "ops",
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
    )


def _update_yaml_artifact(artifact: ProjectArtifact, updater) -> ProjectArtifact:
    try:
        payload = yaml.safe_load(artifact.content)
    except Exception:
        return artifact
    if not isinstance(payload, dict):
        return artifact
    updated = updater(payload)
    if updated == payload:
        return artifact
    return ProjectArtifact(
        path=artifact.path,
        kind=artifact.kind,
        description=artifact.description,
        executable=artifact.executable,
        content=yaml.safe_dump(updated, sort_keys=False, allow_unicode=True),
    )


def _merge_contract_section(payload: dict[str, Any], section: str, values: dict[str, Any]) -> dict[str, Any]:
    updated = dict(payload)
    updated[section] = _deep_merge(_mapping(updated.get(section)), values)
    return updated


def _attach_review_html(
    project: ProjectPlan,
    *,
    request: IntentGenerationRequest,
    schema_source: dict[str, Any],
    provider_proposal_audit: ProviderProposalAudit | None,
    transformation_enrichment: EnrichmentResult | None,
    pre_generation_enrichment: EnrichmentResult | None,
    enrichment: EnrichmentResult | None,
    intent: IntentSpec,
    project_state: ProjectState,
    gap_plan: GapPlan,
    transformation_plan: TransformationPlan,
    context_snapshot: ContextSnapshot,
    generation_signature: GenerationSignature,
    policy_result: GenerationPolicyResult,
    audit_trail: GenerationAuditTrail,
) -> ProjectPlan:
    report = render_intent_generation_review(
        project=project,
        request=request,
        schema_source=schema_source,
        provider_proposal_audit=provider_proposal_audit,
        transformation_enrichment=transformation_enrichment,
        pre_generation_enrichment=pre_generation_enrichment,
        enrichment=enrichment,
        intent=intent,
        project_state=project_state,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
        context_snapshot=context_snapshot,
        generation_signature=generation_signature,
        policy_result=policy_result,
        audit_trail=audit_trail,
    )
    report = translate_report(report, language=request.language, provider=request.provider)
    return ProjectPlan(
        name=project.name,
        target=project.target,
        artifacts=[
            *project.artifacts,
            ProjectArtifact(
                path="AI_REVIEW.html",
                kind="other",
                description="Consolidated rich review for the generated intent-first project.",
                content=report.html,
            ),
        ],
        report=project.report,
        traceability=project.traceability,
    )


def _refine_transformation_plan(
    request: IntentGenerationRequest,
    *,
    intent: IntentSpec,
    gap_plan: GapPlan,
    transformation_plan: TransformationPlan,
    schema_path: str | None,
) -> tuple[TransformationPlan, EnrichmentResult | None, ProviderProposalAudit | None]:
    if request.provider is None or schema_path is None:
        return transformation_plan, None, None

    schema_columns = _schema_column_names(schema_path)
    enrichment = enrich_project_spec(
        {
            "fields": {
                "intent": {"value": intent.to_dict()},
                "gap_plan": {"value": gap_plan.to_dict()},
                "transformation_plan": {"value": transformation_plan.to_dict()},
            }
        },
        request.prompt,
        context_package={"schema_columns": sorted(schema_columns)},
        provider=request.provider,
    )
    if enrichment.status != "ENRICHED" or not enrichment.data:
        return transformation_plan, enrichment, None

    field_updates = enrichment.data.get("field_updates") or {}
    unsupported_decisions = _unsupported_transformation_provider_updates(field_updates)
    proposed_columns = _extract_shape_column_proposals(field_updates)
    proposed_transform = _extract_transform_proposal(field_updates)
    if not proposed_columns:
        if proposed_transform is None:
            return transformation_plan, enrichment, ProviderProposalAudit(
                provider=enrichment.provider,
                prompt=enrichment.prompt,
                decisions=unsupported_decisions,
            )
        transform_value, transform_evidence = proposed_transform
        decisions = list(transformation_plan.decisions_required)
        decisions.append(_provider_transform_review_decision())
        proposal_audit = ProviderProposalAudit(
            provider=enrichment.provider,
            prompt=enrichment.prompt,
            decisions=[
                *unsupported_decisions,
                ProviderProposalDecision(
                    stage="transformation_refinement",
                    field_path="transform",
                    proposed_value=transform_value,
                    outcome="requires_review",
                    rule="transform.provider_structured_block",
                    reason=(
                        "Provider returned a full ContractForge transform block; full transform blocks are always "
                        "review-required because they can change schema, values or row cardinality."
                    ),
                    evidence=transform_evidence,
                )
            ],
        )
        return (
            replace(
                transformation_plan,
                transform=_deep_merge(transformation_plan.transform, transform_value),
                decisions_required=decisions,
            ),
            enrichment,
            proposal_audit,
        )

    existing = transformation_plan.shape_columns
    accepted_steps: list[TransformationStep] = []
    proposal_decisions: list[ProviderProposalDecision] = list(unsupported_decisions)
    warnings = list(transformation_plan.warnings)
    decisions = list(transformation_plan.decisions_required)

    for proposal in proposed_columns:
        target_column = proposal["target_column"]
        source_expression = proposal["source_expression"]
        field_path = f"transform.shape.columns.{target_column}"
        if target_column in existing:
            proposal_decisions.append(
                ProviderProposalDecision(
                    stage="transformation_refinement",
                    field_path=field_path,
                    proposed_value=source_expression,
                    outcome="rejected",
                    rule="shape_column.already_exists",
                    reason="The target column already exists in the deterministic transformation plan.",
                    evidence=proposal["evidence"],
                )
            )
            continue
        outcome, rule, reason = _classify_shape_column_proposal(
            target_column=target_column,
            source_expression=source_expression,
            final_columns=intent.final_columns,
            schema_columns=schema_columns,
            review_required=proposal["review_required"],
        )
        proposal_decisions.append(
            ProviderProposalDecision(
                stage="transformation_refinement",
                field_path=field_path,
                proposed_value=source_expression,
                outcome=outcome,
                rule=rule,
                reason=reason,
                evidence=proposal["evidence"],
            )
        )
        if outcome == "rejected":
            warnings.append(f"Provider suggestion for {target_column!r} was rejected: {reason}")
            continue
        if outcome == "requires_review":
            decisions.append(
                RequiredDecision(
                    question=f"Review provider-suggested projection for {target_column!r}.",
                    reason=reason,
                    path=field_path,
                )
            )
            continue
        accepted_steps.append(
            TransformationStep(
                action="select",
                column=target_column,
                expression=source_expression,
                reason="Provider-reviewed low-risk projection accepted because it references an existing schema column.",
            )
        )

    proposal_audit = ProviderProposalAudit(
        provider=enrichment.provider,
        prompt=enrichment.prompt,
        decisions=proposal_decisions,
    )
    transform_updates: dict[str, Any] = {}
    if proposed_transform is not None:
        transform_value, transform_evidence = proposed_transform
        transform_updates = transform_value
        decisions.append(_provider_transform_review_decision())
        proposal_decisions.append(
            ProviderProposalDecision(
                stage="transformation_refinement",
                field_path="transform",
                proposed_value=transform_value,
                outcome="requires_review",
                rule="transform.provider_structured_block",
                reason=(
                    "Provider returned a full ContractForge transform block; full transform blocks are always "
                    "review-required because they can change schema, values or row cardinality."
                ),
                evidence=transform_evidence,
            )
        )

    if (
        not accepted_steps
        and not transform_updates
        and warnings == transformation_plan.warnings
        and decisions == transformation_plan.decisions_required
    ):
        return transformation_plan, enrichment, proposal_audit
    return (
        replace(
            transformation_plan,
            steps=[*transformation_plan.steps, *accepted_steps],
            transform=_deep_merge(transformation_plan.transform, transform_updates),
            warnings=warnings,
            decisions_required=decisions,
        ),
        enrichment,
        proposal_audit,
    )


def _unsupported_transformation_provider_updates(field_updates: dict[str, Any]) -> list[ProviderProposalDecision]:
    return [
        ProviderProposalDecision(
            stage="transformation_refinement",
            field_path=str(field_path),
            proposed_value=_field_update_value(payload),
            outcome="rejected",
            rule="provider_transformation_field_unsupported",
            reason=(
                "Provider suggested a transformation enrichment field outside the supported ContractForge AI "
                "transformation surface."
            ),
            evidence=_field_update_evidence(payload),
        )
        for field_path, payload in field_updates.items()
        if str(field_path) not in _TRANSFORMATION_PROVIDER_FIELDS
    ]


def _provider_transform_review_decision() -> RequiredDecision:
    return RequiredDecision(
        question="Review provider-suggested ContractForge transform block.",
        reason="Transform blocks can change schema, values or row cardinality and must be reviewed before production use.",
        path="transform",
    )


def _enrich_generation_plan(
    request: IntentGenerationRequest,
    *,
    intent: IntentSpec,
    project_state: ProjectState,
    gap_plan: GapPlan,
    transformation_plan: TransformationPlan,
    context_snapshot: ContextSnapshot,
    generation_signature: GenerationSignature,
    policy_result: GenerationPolicyResult,
) -> EnrichmentResult | None:
    if request.provider is None:
        return None
    return enrich_project_plan(
        {
            "status": "PRE_GENERATION_REVIEW",
            "intent": intent.to_dict(),
            "project_state": project_state.to_dict(),
            "gap_plan": gap_plan.to_dict(),
            "transformation_plan": transformation_plan.to_dict(),
            "context_snapshot": context_snapshot.to_dict(),
            "generation_signature": generation_signature.to_dict(),
            "policy_result": policy_result.to_dict(),
        },
        request.prompt,
        provider=request.provider,
    )


def _enrich_project(project: ProjectPlan, request: IntentGenerationRequest) -> EnrichmentResult | None:
    if request.provider is None:
        return None
    return enrich_project_plan(
        project.to_dict(include_content=False),
        request.prompt,
        provider=request.provider,
    )


def _request_schema_paths(request: IntentGenerationRequest) -> tuple[str, ...]:
    paths: list[str] = []
    if request.schema_path:
        paths.append(request.schema_path)
    paths.extend(str(path) for path in request.schema_paths if str(path).strip())
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        normalized = str(path).strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return tuple(unique)


def _resolve_schema_path(request: IntentGenerationRequest) -> tuple[str | None, dict[str, Any]]:
    schema_paths = _request_schema_paths(request)
    if len(schema_paths) == 1:
        return schema_paths[0], {"kind": "schema_path", "path": schema_paths[0]}
    if request.schema_path:
        return request.schema_path, {"kind": "schema_path", "path": request.schema_path}
    table = request.sample_table or _detect_table_reference(request.prompt)
    if not table:
        return None, {"kind": "missing", "reason": "No schema_path or sample table was provided."}
    try:
        schema = _schema_from_table(table, spark=request.spark)
    except Exception as exc:
        return None, {
            "kind": "sample_table",
            "table": table,
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", prefix="contractforge-ai-table-schema-", delete=False, encoding="utf-8")
    with handle:
        json.dump(schema, handle, indent=2, ensure_ascii=False)
    return handle.name, {"kind": "sample_table", "table": table, "status": "INSPECTED", "schema_path": handle.name}


def _dataset_name_from_schema(schema_path: str) -> str:
    stem = Path(schema_path).stem
    return _safe_name(stem.removesuffix("_schema").removesuffix("_profile"))


def _multi_schema_source_path(source_root: str, dataset: str, *, layer: str, catalog: str) -> str:
    if layer == "silver":
        return f"{catalog}.bronze.{_layer_table('bronze', dataset)}"
    if layer == "gold":
        return f"{catalog}.silver.{_layer_table('silver', dataset)}"
    if source_root in {"", "REVIEW_REQUIRED"}:
        return dataset
    if "{dataset}" in source_root:
        return source_root.replace("{dataset}", dataset)
    if _looks_like_directory_source(source_root):
        return source_root.rstrip("/") + f"/{dataset}"
    if _looks_like_three_part_table(source_root):
        catalog, schema, _ = source_root.split(".", 2)
        return f"{catalog}.{schema}.{dataset}"
    return source_root


def _multi_schema_mode(prompt: str, *, dataset: str, layer: str, intent: IntentSpec) -> str:
    override = _dataset_override(
        prompt,
        dataset,
        (
            "historical",
            "scd2_historical",
            "hash_diff_upsert",
            "scd1_hash_diff",
            "upsert",
            "scd1_upsert",
            "overwrite",
            "scd0_overwrite",
            "append",
            "scd0_append",
        ),
    )
    if override:
        override = {
            "scd2_historical": "historical",
            "scd1_hash_diff": "hash_diff_upsert",
            "scd1_upsert": "upsert",
            "scd0_overwrite": "overwrite",
            "scd0_append": "append",
        }.get(override, override)
        if canonical_write_mode(override) in {"scd1_hash_diff", "scd1_upsert", "scd2_historical"} and layer != "silver":
            return _mode_for_layer(layer, intent.silver_mode)
        return override
    return _mode_for_layer(layer, intent.silver_mode)


def _multi_schema_connector(prompt: str, *, dataset: str, source_path: str) -> str:
    override = _dataset_override(prompt, dataset, ("rest_api", "http_file", "jdbc", "s3", "azure_blob", "table", "files"))
    if override:
        return override
    return _connector_for_source(source_path)


def _dataset_override(prompt: str, dataset: str, values: tuple[str, ...]) -> str | None:
    lowered = prompt.lower()
    aliases = {dataset.lower(), dataset.lower().replace("_", " "), dataset.lower().replace("_", "-")}
    for alias in aliases:
        match = re.search(rf"\b{re.escape(alias)}\b(?P<context>[^.]+)", lowered)
        if not match:
            continue
        context = match.group("context").replace("-", "_").replace(" ", "_")
        for value in values:
            if value in context:
                return value
    return None


def _looks_like_directory_source(value: str) -> bool:
    lowered = value.lower()
    if lowered.startswith(("s3://", "s3a://", "abfs://", "abfss://", "dbfs:/", "/volumes/")):
        suffix = Path(value.rstrip("/")).suffix
        return not suffix
    return False


def _looks_like_three_part_table(value: str) -> bool:
    return re.match(r"^[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*$", value) is not None


def _schema_column_names(schema_path: str) -> set[str]:
    try:
        with open(schema_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return set()
    columns = payload.get("columns") if isinstance(payload, dict) else None
    if not isinstance(columns, list):
        return set()
    return {str(column.get("name")) for column in columns if isinstance(column, dict) and column.get("name")}


def _extract_shape_column_proposals(field_updates: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("shape_columns", "transform.shape.columns"):
        update = field_updates.get(key)
        value = _field_update_value(update)
        if isinstance(value, dict):
            return _shape_column_proposals_from_mapping(value, update)

    shape_update = field_updates.get("shape")
    shape = _field_update_value(shape_update)
    if isinstance(shape, dict):
        columns = shape.get("columns") or shape.get("shape_columns")
        if isinstance(columns, dict):
            return _shape_column_proposals_from_mapping(columns, shape_update)
    return []


def _extract_transform_proposal(field_updates: dict[str, Any]) -> tuple[dict[str, Any], list[str]] | None:
    update = field_updates.get("transform")
    value = _field_update_value(update)
    if not isinstance(value, dict):
        return None
    return value, _field_update_evidence(update)


def _shape_column_proposals_from_mapping(mapping: dict[str, Any], update: Any) -> list[dict[str, Any]]:
    evidence = _field_update_evidence(update)
    review_required = _field_update_review_required(update)
    return [
        {
            "target_column": str(column),
            "source_expression": str(expression),
            "review_required": review_required,
            "evidence": evidence,
        }
        for column, expression in mapping.items()
        if isinstance(expression, str)
    ]


def _field_update_value(update: Any) -> Any:
    if isinstance(update, dict) and "value" in update:
        return update["value"]
    return update


def _field_update_review_required(update: Any) -> bool:
    return isinstance(update, dict) and update.get("review_required") is True


def _field_update_evidence(update: Any) -> list[str]:
    if not isinstance(update, dict):
        return []
    evidence = update.get("evidence")
    if not isinstance(evidence, list):
        return []
    return [str(item) for item in evidence]


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _classify_shape_column_proposal(
    *,
    target_column: str,
    source_expression: str,
    final_columns: list[str],
    schema_columns: set[str],
    review_required: bool,
) -> tuple[str, str, str]:
    checks = (
        (
            review_required,
            "requires_review",
            "shape_column.provider_review_required",
            "The provider marked this transformation suggestion as requiring review.",
        ),
        (
            not _is_safe_identifier(target_column),
            "rejected",
            "shape_column.unsafe_target_identifier",
            "The target column is not a safe unquoted identifier.",
        ),
        (
            bool(final_columns) and target_column not in final_columns,
            "requires_review",
            "shape_column.not_requested",
            "The suggested target column was not requested explicitly in the final-column intent.",
        ),
        (
            source_expression not in schema_columns,
            "requires_review",
            "shape_column.source_not_in_schema",
            f"The source expression {source_expression!r} is not an exact column in the schema evidence.",
        ),
    )
    for condition, outcome, rule, reason in checks:
        if condition:
            return outcome, rule, reason
    return (
        "accepted",
        "shape_column.safe_schema_projection",
        "The suggestion references an explicitly requested target column and an exact source schema column.",
    )


def _is_safe_identifier(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) is not None


def _schema_from_table(table: str, *, spark: SparkLike | None) -> dict[str, Any]:
    spark_session = spark or _active_spark()
    dataframe = spark_session.table(table)
    fields = getattr(getattr(dataframe, "schema", None), "fields", None)
    if fields is None:
        raise ValueError(f"Could not inspect schema fields for table {table!r}.")
    return {
        "columns": [
            {
                "name": str(field.name),
                "type": _field_type(field),
                "nullable": bool(getattr(field, "nullable", True)),
            }
            for field in fields
        ]
    }


def _active_spark() -> SparkLike:
    try:
        from databricks.sdk.runtime import spark
    except Exception as exc:  # pragma: no cover - runtime dependent
        raise RuntimeError(
            "No SparkSession was provided and Databricks runtime spark could not be imported. "
            "Pass --schema or run inside Databricks with an accessible sample table."
        ) from exc
    return spark


def _field_type(field: Any) -> str:
    data_type = getattr(field, "dataType", None)
    if hasattr(data_type, "simpleString"):
        return str(data_type.simpleString()).upper()
    return str(data_type or "STRING").upper()


def _requested_layers(prompt: str) -> list[str]:
    lowered = prompt.lower()
    if "bronze" in lowered and "gold" in lowered:
        return ["bronze", "silver", "gold"]
    if "medallion" in lowered or "bronze to gold" in lowered or "bronze até gold" in lowered:
        return ["bronze", "silver", "gold"]
    return ["single"]


def _detect_single_layer(prompt: str) -> str:
    lowered = prompt.lower()
    for layer in ("bronze", "silver", "gold"):
        if layer in lowered:
            return layer
    return "bronze"


def _detect_table_reference(prompt: str) -> str | None:
    match = re.search(r"\b([A-Za-z_][\w-]*\.[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*)\b", prompt)
    return match.group(1) if match else None


def _catalog(prompt: str, default_catalog: str | None, sample_table: str | None) -> str:
    table = sample_table or _detect_table_reference(prompt)
    if table and table.count(".") == 2:
        return table.split(".")[0]
    return default_catalog or "main"


def _base_name(prompt: str, sample_table: str | None) -> str:
    explicit = re.search(r"(?:project|pipeline|flow)\s+(?:named|called)\s+['\"]?([A-Za-z][\w -]{2,80})", prompt, re.IGNORECASE)
    if explicit:
        return _safe_name(explicit.group(1))
    table = sample_table or _detect_table_reference(prompt)
    if table:
        return _safe_name(table.split(".")[-1].removesuffix("_sample"))
    target = re.search(r"(?:target|to|into)\s+[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*\.([A-Za-z_][\w-]*)", prompt, re.IGNORECASE)
    if target:
        return _safe_name(target.group(1))
    return "generated_project"


def _source(prompt: str, sample_table: str | None) -> str:
    if sample_table:
        return sample_table
    table = _detect_table_reference(prompt)
    if table:
        return table
    uri = re.search(r"\b(s3a?://[^\s,;]+|abfss?://[^\s,;]+|https?://[^\s,;]+|/Volumes/[^\s,;]+|dbfs:/[^\s,;]+)", prompt)
    return uri.group(1).rstrip(".") if uri else "REVIEW_REQUIRED"


def _connector_for_source(source_path: str) -> str:
    lowered = source_path.lower()
    if re.match(r"^[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*$", source_path):
        return "table"
    if lowered.startswith("s3"):
        return "s3"
    if lowered.startswith("abfs"):
        return "azure_blob"
    if lowered.startswith("http"):
        return "http_file"
    if lowered.startswith("jdbc:"):
        return "jdbc"
    return "files"


def _previous_layer(layer: str) -> str:
    return {"silver": "bronze", "gold": "silver"}.get(layer, "bronze")


def _layer_table(layer: str, base_name: str) -> str:
    prefix = {"bronze": "b", "silver": "s", "gold": "g"}[layer]
    clean = _safe_name(base_name)
    return clean if clean.startswith(f"{prefix}_") else f"{prefix}_{clean}"


def _mode_for_layer(layer: str, silver_mode: str) -> str:
    return {
        "bronze": "append",
        "silver": silver_mode,
        "gold": "overwrite",
    }[layer]


def _silver_mode(prompt: str) -> str:
    normalized = prompt.lower().replace("-", "_").replace(" ", "_")
    for mode in ("historical", "scd2_historical", "hash_diff_upsert", "scd1_hash_diff", "upsert", "scd1_upsert", "snapshot_reconcile_soft_delete", "snapshot_soft_delete"):
        if mode in normalized:
            return {
                "scd2_historical": "historical",
                "scd1_hash_diff": "hash_diff_upsert",
                "scd1_upsert": "upsert",
                "snapshot_soft_delete": "snapshot_reconcile_soft_delete",
            }.get(mode, mode)
    if "hash diff" in prompt.lower():
        return "hash_diff_upsert"
    if "upsert" in prompt.lower() or "merge" in prompt.lower():
        return "upsert"
    return "hash_diff_upsert"


def _final_columns(prompt: str) -> list[str]:
    patterns = [
        r"(?:final columns|output columns|selected columns|columns|colunas finais|colunas)\s*[:=]\s*([A-Za-z0-9_,\s.-]+)",
        r"(?:gold.*(?:with|contendo|com))\s+([A-Za-z0-9_,\s.-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            raw = re.split(r"\b(?:using|with|from|into|for|and|e)\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
            return [_safe_name(item) for item in re.split(r"[,;\s]+", raw) if item.strip()]
    return []


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip().lower()).strip("_")
    return cleaned or "generated_project"


def _project_review_markdown(
    project: ProjectPlan,
    *,
    request: IntentGenerationRequest,
    schema_source: dict[str, Any],
    provider_proposal_audit: ProviderProposalAudit | None,
    transformation_enrichment: EnrichmentResult | None,
    pre_generation_enrichment: EnrichmentResult | None,
    enrichment: EnrichmentResult | None,
    intent: IntentSpec,
    project_state: ProjectState,
    gap_plan: GapPlan,
    transformation_plan: TransformationPlan,
    context_snapshot: ContextSnapshot,
    generation_signature: GenerationSignature,
    policy_result: GenerationPolicyResult,
    audit_trail: GenerationAuditTrail,
) -> str:
    lines = [
        "# ContractForge AI Generation Review",
        "",
        "## Executive Summary",
        "",
        f"- Project: `{project.name}`",
        f"- Target: `{project.target}`",
        f"- Generated artifacts: `{len(project.artifacts)}`",
        f"- Schema source: `{schema_source.get('kind')}`",
        f"- Signature hash: `{generation_signature.signature_hash}`",
        f"- Context snapshot: `{context_snapshot.snapshot_hash}`",
        f"- Policy action: `{policy_result.action}`",
        "",
        "## User Intent",
        "",
        request.prompt,
        "",
        "## Interpreted Intent",
        "",
        f"- Requested layers: `{', '.join(intent.requested_layers)}`",
        f"- Source: `{intent.source or 'REVIEW_REQUIRED'}`",
        f"- Target table: `{intent.target_table or 'not specified'}`",
        f"- Final columns: `{', '.join(intent.final_columns) if intent.final_columns else 'not specified'}`",
        f"- Completion goal: `{intent.completion_goal}`",
        "",
        "## Existing Project State",
        "",
        f"- Project root: `{project_state.root or 'not provided'}`",
        f"- Existing layers: `{', '.join(project_state.layers) if project_state.layers else 'none detected'}`",
        f"- Existing contracts: `{len(project_state.contracts)}`",
        "",
        "## Gap Plan",
        "",
        *[
            f"- `{action.layer}`: `{action.action}` - {action.reason}"
            + (f" Existing: `{action.existing_contract}`." if action.existing_contract else "")
            + (f" Source: `{action.source_table}`." if action.source_table else "")
            for action in gap_plan.actions
        ],
        "",
        "## Transformation Plan",
        "",
        f"- Shape projections: `{len(transformation_plan.shape_columns)}`",
        f"- Transformation decisions: `{len(transformation_plan.decisions_required)}`",
        *[
            f"- `{step.column}`: `{step.action}`"
            + (f" from `{step.expression}`" if step.expression else "")
            + (f" - {step.reason}" if step.reason else "")
            for step in transformation_plan.steps
        ],
        "",
        "## Provider-Applied Transformation Updates",
        "",
    ]
    if transformation_enrichment is None:
        lines.append("- No provider was configured for transformation refinement.")
    else:
        lines.extend(
            [
                f"- Status: `{transformation_enrichment.status}`",
                f"- Provider: `{transformation_enrichment.provider}`",
                f"- Prompt: `{transformation_enrichment.prompt}`",
            ]
        )
        if transformation_enrichment.data and transformation_enrichment.data.get("summary"):
            lines.extend(["", str(transformation_enrichment.data["summary"])])
        if transformation_enrichment.warnings:
            lines.extend(["", "Warnings:", *[f"- {warning}" for warning in transformation_enrichment.warnings]])
    lines.extend(["", "## Provider Proposal Audit", ""])
    if provider_proposal_audit is None:
        lines.append("- No provider proposal audit was produced.")
    else:
        lines.extend(
            [
                f"- Action: `{provider_proposal_audit.action}`",
                f"- Accepted: `{provider_proposal_audit.accepted_count}`",
                f"- Rejected: `{provider_proposal_audit.rejected_count}`",
                f"- Requires review: `{provider_proposal_audit.review_required_count}`",
                "",
                *[
                    f"- `{decision.outcome}` `{decision.field_path}` via `{decision.rule}` - {decision.reason}"
                    for decision in provider_proposal_audit.decisions
                ],
            ]
        )
    lines.extend(
        [
            "",
        "## Governance Gate",
        "",
        f"- Policy action: `{policy_result.action}`",
        f"- Findings: `{len(policy_result.findings)}`",
        *[
            f"- `{finding.code}`: `{finding.action}` - {finding.message}"
            + (f" Path: `{finding.path}`." if finding.path else "")
            for finding in policy_result.findings
        ],
        "",
        "## Pre-Generation Provider Guidance",
        "",
        ]
    )
    if pre_generation_enrichment is None:
        lines.append("- No provider was configured before artifact generation.")
    else:
        lines.extend(
            [
                f"- Status: `{pre_generation_enrichment.status}`",
                f"- Provider: `{pre_generation_enrichment.provider}`",
                f"- Prompt: `{pre_generation_enrichment.prompt}`",
            ]
        )
        if pre_generation_enrichment.data:
            if pre_generation_enrichment.data.get("summary"):
                lines.extend(["", str(pre_generation_enrichment.data["summary"])])
            recommendations = pre_generation_enrichment.data.get("recommendations") or []
            if recommendations:
                lines.extend(["", "Recommendations:", *[f"- {item}" for item in recommendations]])
            decisions = pre_generation_enrichment.data.get("decisions_required") or []
            if decisions:
                lines.extend(["", "Provider-identified decisions:", *[f"- {item}" for item in decisions]])
        if pre_generation_enrichment.warnings:
            lines.extend(["", "Warnings:", *[f"- {warning}" for warning in pre_generation_enrichment.warnings]])
    lines.extend(
        [
            "",
            "## Generation Audit",
            "",
            f"- Events: `{len(audit_trail.events)}`",
            f"- Last hash: `{audit_trail.last_hash or 'none'}`",
            *[f"- `{event.stage}` -> `{event.outcome}` (`{event.event_hash}`)" for event in audit_trail.events],
            "",
            "## Generated Implementation Artifacts",
            "",
            *[f"- `{artifact.path}` ({artifact.kind}) - {artifact.description or 'generated artifact'}" for artifact in project.artifacts],
            "",
            "## Review Decisions",
            "",
        ]
    )
    if project.report.decisions_required:
        lines.extend(item.to_markdown() for item in project.report.decisions_required)
    else:
        lines.append("- No blocking decisions were produced by deterministic generation.")
    if project.report.warnings:
        lines.extend(["", "## Warnings", "", *[f"- {warning}" for warning in project.report.warnings]])
    lines.extend(["", "## Traceability", "", project.traceability.to_markdown().rstrip()])
    if enrichment is not None:
        lines.extend(["", "## Post-Generation Provider Guidance", "", f"- Status: `{enrichment.status}`", f"- Provider: `{enrichment.provider}`"])
        if enrichment.data and enrichment.data.get("summary"):
            lines.extend(["", str(enrichment.data["summary"])])
        if enrichment.warnings:
            lines.extend(["", "Warnings:", *[f"- {warning}" for warning in enrichment.warnings]])
    return "\n".join(lines).rstrip() + "\n"


def _missing_schema_markdown(request: IntentGenerationRequest, schema_source: dict[str, Any]) -> str:
    return (
        "# ContractForge AI Generation Review\n\n"
        "## Status\n\n"
        "- Status: `NEEDS_DECISIONS`\n"
        "- Reason: schema evidence is required before generating contracts.\n\n"
        "## User Intent\n\n"
        f"{request.prompt}\n\n"
        "## Schema Evidence\n\n"
        f"```json\n{json.dumps(schema_source, indent=2, ensure_ascii=False)}\n```\n\n"
        "## Required Decision\n\n"
        "- Provide `--schema` with a schema/profile file, or run inside Databricks with `--sample-table` pointing to an accessible table.\n"
    )
