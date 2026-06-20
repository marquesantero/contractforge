"""Guided project generation from planner intent."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import yaml

from contractforge_ai.agentic.governance import (
    ContextSnapshot,
    GenerationAuditTrail,
    GenerationPolicyEngine,
    GenerationPolicyResult,
    GenerationSignature,
    ProviderProposalAudit,
    ProviderProposalDecision,
    ProviderProposalOutcome,
)
from contractforge_ai.agentic.models import GapAction, GapPlan, IntentSpec, ProjectState, TransformationPlan
from contractforge_ai.context import ProjectContextPackage, build_project_context_package, schema_profile_to_yaml
from contractforge_ai.enrichment import EnrichmentResult, enrich_project_spec
from contractforge_ai.generators.project import (
    generate_project_for_target,
)
from contractforge_ai.generators.targets import project_target_spec_bindings
from contractforge_ai.models import EvidenceItem, Traceability
from contractforge_ai.planning import EnrichedProjectSpec, ProjectPlannerRequest, ProjectPlannerResult, plan_project_from_intent
from contractforge_ai.planning.spec import PROVIDER_UPDATABLE_FIELDS, SpecValue
from contractforge_ai.projects.artifact_policy import compact_human_review_artifacts, split_human_review_artifacts
from contractforge_ai.projects.models import DecisionReport, ProjectArtifact, ProjectPlan
from contractforge_ai.providers import ModelProvider
from contractforge_ai.intelligence import CritiqueReport, critique_output
from contractforge_ai.reports import render_guided_project_review
from contractforge_ai.reports_translation import translate_report
from contractforge_ai.validation import DeterministicValidationReport, validate_project_plan_artifact

GuidedProjectStatus = Literal["READY", "NEEDS_DECISIONS", "INVALID", "UNSAFE"]
GuidedProjectTarget = Literal[
    "contractforge-yaml",
    "contractforge-python",
    "databricks-dab",
    "aws-glue-iceberg",
    "dbt",
    "classic-pyspark",
]


@dataclass(frozen=True)
class GuidedProjectRequest:
    """Inputs for planner-driven project generation."""

    intent: str
    schema_path: str | None = None
    context_dir: str | None = None
    runtime: str | None = None
    default_catalog: str | None = None
    default_schema: str | None = None
    default_layer: str | None = None
    preferred_target: GuidedProjectTarget | None = None
    allow_review_required: bool = False
    language: str = "en"
    naming: dict[str, Any] | None = None
    provider: ModelProvider | None = None
    contractforge_capabilities: dict[str, Any] | None = None


@dataclass(frozen=True)
class GuidedProjectResult:
    """Result of resolving a guided project request."""

    status: GuidedProjectStatus
    planner: ProjectPlannerResult
    selected_target: str | None
    project: ProjectPlan | None = None
    context: ProjectContextPackage | None = None
    spec: EnrichedProjectSpec | None = None
    spec_enrichment: EnrichmentResult | None = None
    validation: DeterministicValidationReport | None = None
    critique: CritiqueReport | None = None
    context_snapshot: ContextSnapshot | None = None
    generation_signature: GenerationSignature | None = None
    policy_result: GenerationPolicyResult | None = None
    audit_trail: GenerationAuditTrail | None = None
    provider_proposal_audit: ProviderProposalAudit | None = None

    @property
    def ready(self) -> bool:
        return self.status == "READY" and self.project is not None

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return {
            "status": self.status,
            "selected_target": self.selected_target,
            "planner": self.planner.to_dict(),
            "spec": self.spec.to_dict() if self.spec else None,
            "spec_enrichment": self.spec_enrichment.to_dict() if self.spec_enrichment else None,
            "project": self.project.to_dict(include_content=include_content) if self.project else None,
            "context": self.context.to_dict() if self.context else None,
            "validation": self.validation.to_dict() if self.validation else None,
            "critique": self.critique.to_dict() if self.critique else None,
            "context_snapshot": self.context_snapshot.to_dict() if self.context_snapshot else None,
            "generation_signature": self.generation_signature.to_dict() if self.generation_signature else None,
            "policy_result": self.policy_result.to_dict() if self.policy_result else None,
            "audit_trail": self.audit_trail.to_dict() if self.audit_trail else None,
            "provider_proposal_audit": self.provider_proposal_audit.to_dict() if self.provider_proposal_audit else None,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Guided Project Result",
            "",
            f"- Status: `{self.status}`",
            f"- Selected target: `{self.selected_target or 'REVIEW_REQUIRED'}`",
            "",
            self.planner.to_markdown().rstrip(),
        ]
        if self.project is not None:
            lines.extend(["", self.project.to_markdown().rstrip()])
        if self.spec is not None:
            lines.extend(["", "## Enriched Specification", "", f"- Validation: `{self.spec.validate().status}`"])
        if self.spec_enrichment is not None:
            lines.extend(["", "## Provider Specification Enrichment", "", f"- Status: `{self.spec_enrichment.status}`"])
        if self.context is not None:
            lines.extend(["", self.context.to_markdown().rstrip()])
        if self.validation is not None:
            lines.extend(["", self.validation.to_markdown().rstrip()])
        if self.critique is not None:
            lines.extend(["", self.critique.to_markdown().rstrip()])
        return "\n".join(lines).rstrip() + "\n"


def generate_guided_project(request: GuidedProjectRequest) -> GuidedProjectResult:
    """Plan and optionally materialize a ProjectPlan from guided natural-language intent."""

    context = build_project_context_package(
        intent=request.intent,
        context_dir=request.context_dir,
        schema_path=request.schema_path,
        runtime=request.runtime,
    )
    schema_path = request.schema_path
    if not schema_path and context.inferred_schema:
        return _generate_with_inferred_schema(request, context)
    if not schema_path:
        planner = plan_project_from_intent(
            ProjectPlannerRequest(
                intent=request.intent,
                schema_path=None,
                default_catalog=request.default_catalog,
                default_schema=request.default_schema,
                default_layer=request.default_layer,
                preferred_target=request.preferred_target,
            )
        )
        return GuidedProjectResult(
            status="NEEDS_DECISIONS",
            planner=planner,
            selected_target=_select_target(planner, request.preferred_target),
            context=context,
        )

    return _generate_with_schema_path(request, schema_path, context)


def _generate_with_inferred_schema(
    request: GuidedProjectRequest,
    context: ProjectContextPackage,
) -> GuidedProjectResult:
    with tempfile.TemporaryDirectory(prefix="contractforge-ai-context-") as tmp_dir:
        schema_file = Path(tmp_dir) / "inferred-schema-profile.yaml"
        schema_file.write_text(schema_profile_to_yaml(context.inferred_schema or {}), encoding="utf-8")
        return _generate_with_schema_path(request, str(schema_file), context)


def _generate_with_schema_path(
    request: GuidedProjectRequest,
    schema_path: str,
    context: ProjectContextPackage,
) -> GuidedProjectResult:
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=request.intent,
            schema_path=schema_path,
            default_catalog=request.default_catalog,
            default_schema=request.default_schema,
            default_layer=request.default_layer,
            preferred_target=request.preferred_target,
        )
    )
    selected_target = _select_target(planner, request.preferred_target)
    spec, spec_enrichment = _build_enriched_spec(request, planner, selected_target, context)
    governance = _build_guided_governance(
        request=request,
        planner=planner,
        selected_target=selected_target,
        context=context,
        spec=spec,
        spec_enrichment=spec_enrichment,
    )
    spec_validation = spec.validate()
    if spec_validation.status == "NEEDS_DECISIONS" and not request.allow_review_required:
        return GuidedProjectResult(
            status="NEEDS_DECISIONS",
            planner=planner,
            selected_target=selected_target,
            context=context,
            spec=spec,
            spec_enrichment=spec_enrichment,
            **governance,
        )

    project = _generate_project_from_spec(spec, selected_target, schema_path=schema_path, naming=request.naming)
    project = _attach_context_artifacts(project, context)
    validation = validate_project_plan_artifact(project, use_contractforge=False)
    critique = critique_output(
        project.to_dict(include_content=False),
        validation=validation,
        context_results=[item.to_dict() for item in context.files],
    )
    result = GuidedProjectResult(
        status=_guided_status(planner, validation, critique),
        planner=planner,
        selected_target=selected_target,
        project=project,
        context=context,
        spec=spec,
        spec_enrichment=spec_enrichment,
        validation=validation,
        critique=critique,
        **governance,
    )
    return _with_review_artifacts(result, request=request)


def _select_target(planner: ProjectPlannerResult, preferred_target: str | None) -> str:
    if preferred_target:
        return preferred_target
    if not planner.recommendations:
        return "contractforge-yaml"
    return planner.recommendations[0].target


def _build_enriched_spec(
    request: GuidedProjectRequest,
    planner: ProjectPlannerResult,
    selected_target: str,
    context: ProjectContextPackage,
) -> tuple[EnrichedProjectSpec, EnrichmentResult | None]:
    spec = EnrichedProjectSpec.from_planner(planner, selected_target=selected_target)
    if request.provider is None:
        return spec, None

    enrichment = enrich_project_spec(
        spec.to_dict(),
        request.intent,
        context_package=context.to_dict(),
        contractforge_capabilities=request.contractforge_capabilities,
        provider=request.provider,
    )
    if enrichment.status == "ENRICHED" and enrichment.data is not None:
        return spec.with_provider_enrichment(enrichment.data), enrichment
    return spec, enrichment


def _build_guided_governance(
    *,
    request: GuidedProjectRequest,
    planner: ProjectPlannerResult,
    selected_target: str,
    context: ProjectContextPackage,
    spec: EnrichedProjectSpec,
    spec_enrichment: EnrichmentResult | None,
) -> dict[str, Any]:
    """Build CFA governance primitives for the guided generation path."""

    audit = GenerationAuditTrail()
    intent = _guided_intent_spec(request=request, planner=planner, selected_target=selected_target, spec=spec)
    project_state = ProjectState(root=context.context_dir)
    gap_plan = GapPlan(
        actions=[
            GapAction(
                action="generate",
                layer=_safe_layer(intent.requested_layers[0] if intent.requested_layers else "bronze"),
                reason="Guided project generation selected this layer from the interpreted request.",
            )
        ],
        decisions_required=[*intent.decisions_required, *spec.validate().decisions_required],
        warnings=spec.validate().warnings,
    )
    transformation_plan = TransformationPlan(transform=_spec_transform_payload(spec))
    context_snapshot = ContextSnapshot(
        project_state=project_state,
        schema_source={
            "kind": "guided_project_context",
            "schema_path": request.schema_path or context.schema_path,
            "context_dir": context.context_dir,
            "has_inferred_schema": context.inferred_schema is not None,
            "files": [item.to_dict() for item in context.files],
        },
    )
    signature = GenerationSignature(
        intent=intent,
        context_snapshot=context_snapshot,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
    )
    policy_result = GenerationPolicyEngine().evaluate(signature)
    audit.record("guided_intent_planning", planner.status, selected_target=selected_target)
    audit.record("guided_context_packaging", "resolved", files=len(context.files), inferred_schema=context.inferred_schema is not None)
    audit.record("guided_spec_enrichment", spec_enrichment.status if spec_enrichment else "not_requested")
    audit.record("guided_policy_evaluation", policy_result.action, findings=[finding.code for finding in policy_result.findings])

    return {
        "context_snapshot": context_snapshot,
        "generation_signature": signature,
        "policy_result": policy_result,
        "audit_trail": audit,
        "provider_proposal_audit": _provider_audit_from_spec_enrichment(spec_enrichment, spec),
    }


def _guided_intent_spec(
    *,
    request: GuidedProjectRequest,
    planner: ProjectPlannerResult,
    selected_target: str,
    spec: EnrichedProjectSpec,
) -> IntentSpec:
    intent = planner.intent
    layer = _safe_layer(getattr(intent, "layer", None) or "bronze")
    target = ".".join(
        item
        for item in [
            getattr(intent, "target_catalog", None),
            getattr(intent, "target_schema", None),
            getattr(intent, "target_table", None),
        ]
        if item
    )
    return IntentSpec(
        prompt=request.intent,
        requested_layers=[layer],
        source=getattr(intent, "source_path", None),
        target_table=target or getattr(intent, "target_table", None),
        base_name=getattr(intent, "project_name", None) or getattr(intent, "target_table", None) or "contractforge_project",
        catalog=getattr(intent, "target_catalog", None) or request.default_catalog or "main",
        quality_rules=_spec_field_value(spec.quality_rules, default={}),
        operations=_spec_field_value(spec.operations, default={}),
        dab_compute=_spec_field_value(spec.dab_compute, default={}),
        silver_mode=getattr(intent, "mode", None) or "hash_diff_upsert",
        output_target=selected_target,
        decisions_required=planner.traceability.decisions_required,
        evidence=planner.traceability.evidence,
        confidence=planner.traceability.confidence,
    )


def _safe_layer(value: Any) -> str:
    return str(value).lower() if str(value).lower() in {"bronze", "silver", "gold"} else "bronze"


def _spec_field_value(field: Any, *, default: Any) -> Any:
    return getattr(field, "value", default) if field is not None else default


def _spec_transform_payload(spec: EnrichedProjectSpec) -> dict[str, Any]:
    transform = _canonical_transform_payload(_mapping(_spec_field_value(spec.transform, default={})))
    shape = _canonical_shape_payload(_mapping(_spec_field_value(spec.shape, default={})))
    if shape:
        transform = _deep_merge(transform, {"shape": shape})
    return transform


def _provider_audit_from_spec_enrichment(
    spec_enrichment: EnrichmentResult | None,
    spec: EnrichedProjectSpec,
) -> ProviderProposalAudit | None:
    if spec_enrichment is None or not isinstance(spec_enrichment.data, dict):
        return None
    field_updates = spec_enrichment.data.get("field_updates")
    if not isinstance(field_updates, dict):
        return None
    decisions: list[ProviderProposalDecision] = []
    decision_paths = {decision.path for decision in spec.decisions_required if decision.path}
    for field_path, raw_payload in field_updates.items():
        payload = raw_payload if isinstance(raw_payload, dict) else {"value": raw_payload}
        proposed_value = payload.get("value")
        review_required = bool(payload.get("review_required", False))
        final_field = getattr(spec, str(field_path), None)
        applied = isinstance(final_field, SpecValue) and final_field.source == "provider" and final_field.value == proposed_value
        unsupported = str(field_path) not in PROVIDER_UPDATABLE_FIELDS
        rejected = unsupported or (not applied and str(field_path) in decision_paths)
        requires_review = (applied and final_field.review_required) or (str(field_path) in decision_paths and not rejected)
        if rejected:
            outcome: ProviderProposalOutcome = "rejected"
            rule = "provider_spec_field_update_rejected"
            reason = "Provider field update was not applied to the guided specification."
        elif requires_review or review_required:
            outcome = "requires_review"
            rule = "provider_spec_field_update_review_boundary"
            reason = "Provider field update requires human review before use."
        else:
            outcome = "accepted"
            rule = "provider_spec_field_update_allowed"
            reason = "Provider field update was accepted into the guided specification draft."
        decisions.append(
            ProviderProposalDecision(
                stage="guided_spec_enrichment",
                field_path=str(field_path),
                proposed_value=proposed_value,
                outcome=outcome,
                rule=rule,
                reason=reason,
                evidence=[str(item) for item in payload.get("evidence", [])] if isinstance(payload.get("evidence"), list) else [],
            )
        )
    return ProviderProposalAudit(
        provider=spec_enrichment.provider,
        prompt=spec_enrichment.prompt,
        decisions=decisions,
    )


def _generate_project(
    planner: ProjectPlannerResult,
    selected_target: str,
    *,
    schema_path: str,
    naming: dict[str, Any] | None,
) -> ProjectPlan:
    intent = planner.intent
    kwargs = {
        "project_name": intent.project_name or intent.target_table or "contractforge_project",
        "connector": intent.connector or "REVIEW_REQUIRED",
        "source_path": intent.source_path or "REVIEW_REQUIRED",
        "target_catalog": intent.target_catalog or "REVIEW_REQUIRED",
        "target_schema": intent.target_schema or "REVIEW_REQUIRED",
        "target_table": intent.target_table or "REVIEW_REQUIRED",
        "layer": intent.layer or "bronze",
        "mode": intent.mode,
        "owner": intent.owner,
        "naming": naming,
    }

    return generate_project_for_target(selected_target, schema_path, **kwargs)


def _generate_project_from_spec(
    spec: EnrichedProjectSpec,
    selected_target: str,
    *,
    schema_path: str,
    naming: dict[str, Any] | None,
) -> ProjectPlan:
    kwargs = {
        **spec.generation_kwargs(),
        "naming": naming,
        **_target_bound_generation_kwargs(spec, selected_target),
    }
    project = generate_project_for_target(selected_target, schema_path, **kwargs)
    return _apply_spec_overrides(project, spec, selected_target=selected_target)


def _target_bound_generation_kwargs(spec: EnrichedProjectSpec, selected_target: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for binding in project_target_spec_bindings(selected_target):
        field = getattr(spec, binding.spec_field, None)
        if field is not None:
            values[binding.kwarg] = field.value
    return values


def _apply_spec_overrides(project: ProjectPlan, spec: EnrichedProjectSpec, *, selected_target: str) -> ProjectPlan:
    artifacts = [_apply_artifact_spec_overrides(artifact, spec, selected_target=selected_target) for artifact in project.artifacts]
    if artifacts == project.artifacts:
        return project
    return ProjectPlan(
        name=project.name,
        target=project.target,
        artifacts=artifacts,
        report=project.report,
        traceability=project.traceability,
    )


def _apply_artifact_spec_overrides(artifact: ProjectArtifact, spec: EnrichedProjectSpec, *, selected_target: str) -> ProjectArtifact:
    if artifact.path.endswith(".ingestion.yaml"):
        return _update_yaml_artifact(artifact, lambda payload: _apply_ingestion_spec(payload, spec, selected_target=selected_target))
    if artifact.path.endswith(".annotations.yaml") and spec.annotations is not None:
        return _update_yaml_artifact(
            artifact,
            lambda payload: _deep_merge(payload, _mapping(spec.annotations.value)),
        )
    if artifact.path.endswith(".operations.yaml") and spec.operations is not None:
        return _update_yaml_artifact(
            artifact,
            lambda payload: _deep_merge(payload, _mapping(spec.operations.value)),
        )
    return artifact


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
    return replace(artifact, content=yaml.safe_dump(updated, sort_keys=False, allow_unicode=True))


def _apply_ingestion_spec(payload: dict[str, Any], spec: EnrichedProjectSpec, *, selected_target: str) -> dict[str, Any]:
    updated = dict(payload)
    source = dict(_mapping(updated.get("source")))
    if spec.source_format is not None:
        source["format"] = spec.source_format.value
    if source:
        updated["source"] = source
    if spec.merge_keys is not None:
        updated["merge_keys"] = spec.merge_keys.value
    if spec.hash_columns is not None:
        updated["hash_keys"] = spec.hash_columns.value
    if spec.quality_rules is not None:
        updated["quality_rules"] = _deep_merge(_mapping(updated.get("quality_rules")), _mapping(spec.quality_rules.value))
    supports_transform = _target_supports_transform(selected_target)
    if supports_transform and spec.transform is not None:
        shape_schema_policy = _shape_schema_policy(_mapping(spec.transform.value))
        if shape_schema_policy is not None and not updated.get("schema_policy"):
            updated["schema_policy"] = shape_schema_policy
        updated["transform"] = _deep_merge(
            _mapping(updated.get("transform")),
            _canonical_transform_payload(_mapping(spec.transform.value)),
        )
    if supports_transform and spec.shape is not None:
        shape_schema_policy = _shape_schema_policy(_mapping(spec.shape.value))
        if shape_schema_policy is not None and not updated.get("schema_policy"):
            updated["schema_policy"] = shape_schema_policy
        transform = dict(_mapping(updated.get("transform")))
        shape = _deep_merge(
            _canonical_shape_payload(_mapping(transform.get("shape"))),
            _canonical_shape_payload(_mapping(spec.shape.value)),
        )
        if shape:
            transform["shape"] = shape
        else:
            transform.pop("shape", None)
        updated["transform"] = transform
    return updated


def _target_supports_transform(selected_target: str) -> bool:
    if selected_target == "gcp-bigquery":
        try:
            from contractforge_gcp.capabilities import gcp_bigquery_capabilities
        except Exception:
            return False
        capabilities = gcp_bigquery_capabilities()
        return bool(getattr(capabilities, "supports_transform", False) or getattr(capabilities, "supports_shape", False))
    return True


def _canonical_transform_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "shape" not in payload:
        return payload
    updated = dict(payload)
    shape = _canonical_shape_payload(_mapping(updated.get("shape")))
    if shape:
        updated["shape"] = shape
    else:
        updated.pop("shape", None)
    return updated


def _canonical_shape_payload(payload: dict[str, Any]) -> dict[str, Any]:
    updated = dict(payload)
    updated.pop("type", None)
    updated.pop("schema_policy", None)
    parse_json = updated.get("parse_json")
    if isinstance(parse_json, dict):
        parse_columns = parse_json.get("columns") or parse_json.get("shape_columns")
        if isinstance(parse_columns, list):
            existing_columns = _canonical_columns_payload(updated.get("columns"))
            updated["columns"] = {**existing_columns, **_canonical_columns_payload(parse_columns)}
            updated.pop("parse_json", None)
        else:
            updated["parse_json"] = [parse_json]
    if isinstance(updated.get("parse_json"), list):
        parse_json_items = [_canonical_parse_json_item(item) for item in updated["parse_json"]]
        parse_json_items = [item for item in parse_json_items if item is not None]
        if parse_json_items:
            updated["parse_json"] = parse_json_items
        else:
            updated.pop("parse_json", None)
    if isinstance(updated.get("flatten"), list):
        flatten_items = [item for item in updated["flatten"] if isinstance(item, dict)]
        if flatten_items:
            updated["flatten"] = flatten_items[0]
        else:
            updated.pop("flatten", None)
    for key in ("zip_arrays", "arrays"):
        if isinstance(updated.get(key), dict):
            updated[key] = [updated[key]]
    columns = updated.get("columns")
    if isinstance(columns, list):
        updated["columns"] = _canonical_columns_payload(columns)
    elif isinstance(columns, dict):
        updated["columns"] = _canonical_columns_payload(columns)
    if updated.get("columns") == {}:
        updated.pop("columns", None)
    return {key: value for key, value in updated.items() if key in {"columns", "parse_json", "flatten", "zip_arrays", "arrays"}}


def _shape_schema_policy(payload: dict[str, Any]) -> Any | None:
    shape = payload.get("shape") if "shape" in payload else payload
    if not isinstance(shape, dict):
        return None
    value = shape.get("schema_policy")
    return value if value not in (None, "") else None


def _canonical_columns_payload(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items() if str(key).strip() and str(item).strip()}
    if not isinstance(value, list):
        return {}
    return {
        str(column): str(column)
        for column in value
        if isinstance(column, str) and column.strip()
    }


def _canonical_parse_json_item(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    item = dict(value)
    if not item.get("column") and item.get("source_column"):
        item["column"] = item.pop("source_column")
    if not item.get("alias") and item.get("target_column"):
        item["alias"] = item.pop("target_column")
    if not item.get("column") or not (item.get("schema") or item.get("schema_ref")):
        return None
    return item


def _merge_contract_section(payload: dict[str, Any], section: str, values: dict[str, Any]) -> dict[str, Any]:
    if not values:
        return payload
    updated = dict(payload)
    updated[section] = _deep_merge(_mapping(updated.get(section)), values)
    return updated


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


def _attach_context_artifacts(project: ProjectPlan, context: ProjectContextPackage) -> ProjectPlan:
    if not context.context_dir and not context.schema_path and not context.inferred_schema:
        return project

    context_artifacts = [
        ProjectArtifact(
            path="CONTEXT.md",
            kind="markdown",
            description="Project synthesis context summary.",
            content=context.to_markdown(),
        ),
        ProjectArtifact(
            path="context/context-package.json",
            kind="json",
            description="Machine-readable context package used for synthesis.",
            content=json.dumps(context.to_dict(), indent=2, ensure_ascii=False),
        ),
    ]
    if context.inferred_schema and not context.schema_path:
        context_artifacts.append(
            ProjectArtifact(
                path="context/inferred-schema-profile.yaml",
                kind="yaml",
                description="Schema profile inferred from local context samples.",
                content=schema_profile_to_yaml(context.inferred_schema),
            )
        )

    return ProjectPlan(
        name=project.name,
        target=project.target,
        artifacts=[*project.artifacts, *context_artifacts],
        report=DecisionReport(
            title=project.report.title,
            summary=f"{project.report.summary} Context evidence was attached for review.",
            assumptions=project.report.assumptions,
            decisions_required=[*project.report.decisions_required, *context.decisions_required],
            warnings=[*project.report.warnings, *context.warnings],
        ),
        traceability=Traceability(
            confidence=min(project.traceability.confidence, context.traceability.confidence),
            evidence=[
                *project.traceability.evidence,
                EvidenceItem(
                    source="project_context",
                    path=context.context_dir,
                    reason="Attached context package to generated project artifacts.",
                    value={
                        "files": len(context.files),
                        "runtime": context.runtime,
                        "has_inferred_schema": context.inferred_schema is not None,
                    },
                    confidence=context.traceability.confidence,
                ),
            ],
            assumptions=project.traceability.assumptions,
            decisions_required=[*project.traceability.decisions_required, *context.decisions_required],
            review_required=True,
        ),
    )


def _with_review_artifacts(result: GuidedProjectResult, *, request: GuidedProjectRequest) -> GuidedProjectResult:
    if result.project is None:
        return result
    split = split_human_review_artifacts(result.project.artifacts, extra_paths={"README.md"})
    compact_project = _project_with_artifacts(result.project, split.kept)
    compact_result = GuidedProjectResult(
        status=result.status,
        planner=result.planner,
        selected_target=result.selected_target,
        project=compact_project,
        context=result.context,
        spec=result.spec,
        spec_enrichment=result.spec_enrichment,
        validation=result.validation,
        critique=result.critique,
        context_snapshot=result.context_snapshot,
        generation_signature=result.generation_signature,
        policy_result=result.policy_result,
        audit_trail=result.audit_trail,
        provider_proposal_audit=result.provider_proposal_audit,
    )
    review = render_guided_project_review(compact_result, consolidated_artifacts=split.consolidated)
    review = translate_report(review, language=request.language, provider=request.provider)
    project = _append_review_artifacts(compact_project, review.markdown, review.html)
    return GuidedProjectResult(
        status=result.status,
        planner=result.planner,
        selected_target=result.selected_target,
        project=project,
        context=result.context,
        spec=result.spec,
        spec_enrichment=result.spec_enrichment,
        validation=result.validation,
        critique=result.critique,
        context_snapshot=result.context_snapshot,
        generation_signature=result.generation_signature,
        policy_result=result.policy_result,
        audit_trail=result.audit_trail,
        provider_proposal_audit=result.provider_proposal_audit,
    )


def _compact_project(project: ProjectPlan) -> ProjectPlan:
    compact_artifacts = compact_human_review_artifacts(project.artifacts)
    if len(compact_artifacts) == len(project.artifacts):
        return project
    return _project_with_artifacts(project, compact_artifacts)


def _project_with_artifacts(project: ProjectPlan, artifacts: list[ProjectArtifact]) -> ProjectPlan:
    return ProjectPlan(
        name=project.name,
        target=project.target,
        artifacts=artifacts,
        report=project.report,
        traceability=project.traceability,
    )


def _append_review_artifacts(project: ProjectPlan, markdown: str, html: str) -> ProjectPlan:
    del markdown
    compact_artifacts = compact_human_review_artifacts(project.artifacts)
    existing = {artifact.path for artifact in compact_artifacts}
    review_artifacts = []
    if "AI_REVIEW.html" not in existing:
        review_artifacts.append(
            ProjectArtifact(
                path="AI_REVIEW.html",
                kind="other",
                description="Self-contained rich ContractForge AI review report.",
                content=html,
            )
        )
    if not review_artifacts and len(compact_artifacts) == len(project.artifacts):
        return project
    return ProjectPlan(
        name=project.name,
        target=project.target,
        artifacts=[*compact_artifacts, *review_artifacts],
        report=project.report,
        traceability=project.traceability,
    )


def _guided_status(
    planner: ProjectPlannerResult,
    validation: DeterministicValidationReport,
    critique: CritiqueReport,
) -> GuidedProjectStatus:
    if validation.status == "UNSAFE" or critique.status == "UNSAFE":
        return "UNSAFE"
    if validation.status == "INVALID" or critique.status == "INVALID":
        return "INVALID"
    if planner.status != "READY_FOR_REVIEW" or validation.status == "NEEDS_DECISIONS" or critique.status == "NEEDS_DECISIONS":
        return "NEEDS_DECISIONS"
    return "READY"
