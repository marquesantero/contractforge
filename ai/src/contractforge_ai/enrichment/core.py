"""Provider-neutral enrichment orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

from contractforge_ai.context.redaction import redact_secrets
from contractforge_ai.evaluation import render_prompt, validate_model_output
from contractforge_ai.generators.targets import supported_project_targets
from contractforge_ai.providers import GenerationOptions, ModelProvider, ProviderExecutionError

EnrichmentStatus = Literal["ENRICHED", "SKIPPED", "FAILED"]

PROTECTED_DETERMINISTIC_FIELDS = {
    "adapter_status",
    "blockers",
    "findings",
    "planning_status",
    "planner_status",
    "ready",
    "status",
    "support_status",
    "supported",
    "traceability",
    "unsupported",
    "validation_status",
    "warnings",
}


@dataclass(frozen=True)
class EnrichmentResult:
    """Optional enrichment result attached to deterministic output."""

    status: EnrichmentStatus
    prompt: str
    provider: str
    data: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "prompt": self.prompt,
            "provider": self.provider,
            "data": self.data,
            "warnings": self.warnings,
        }


def enrich_review_result(
    deterministic_result: dict[str, Any],
    contract: dict[str, Any],
    *,
    provider: ModelProvider,
    options: GenerationOptions | None = None,
) -> EnrichmentResult:
    """Enrich a deterministic review result with a model provider."""

    return _enrich(
        prompt_name="review.enrichment.v1",
        variables={
            "deterministic_result": deterministic_result,
            "contract_excerpt": contract,
        },
        provider=provider,
        options=options,
        deterministic_fallback=deterministic_result,
    )


def enrich_failure_explanation(
    deterministic_explanation: dict[str, Any],
    evidence: dict[str, Any],
    *,
    provider: ModelProvider,
    options: GenerationOptions | None = None,
) -> EnrichmentResult:
    """Enrich a deterministic failure explanation with a model provider."""

    return _enrich(
        prompt_name="explain.enrichment.v1",
        variables={
            "deterministic_explanation": deterministic_explanation,
            "redacted_evidence": redact_secrets(evidence),
        },
        provider=provider,
        options=options,
        deterministic_fallback=deterministic_explanation,
    )


def enrich_project_plan(
    deterministic_plan: dict[str, Any],
    user_intent: str,
    *,
    provider: ModelProvider,
    options: GenerationOptions | None = None,
) -> EnrichmentResult:
    """Enrich a deterministic project-planning result with a model provider."""

    return _enrich(
        prompt_name="project.plan.enrichment.v1",
        variables={
            "project_plan": deterministic_plan,
            "user_intent": user_intent,
        },
        provider=provider,
        options=options,
        deterministic_fallback=deterministic_plan,
    )


def enrich_adapter_validation(
    adapter_validation: dict[str, Any],
    *,
    project_context: dict[str, Any] | None = None,
    user_intent: str = "",
    provider: ModelProvider,
    options: GenerationOptions | None = None,
) -> EnrichmentResult:
    """Enrich deterministic adapter planning validation with advisory guidance."""

    return _enrich(
        prompt_name="adapter.validation.enrichment.v1",
        variables={
            "adapter_validation": adapter_validation,
            "project_context": project_context or {},
            "user_intent": user_intent,
        },
        provider=provider,
        options=options,
        deterministic_fallback=adapter_validation,
    )


def enrich_project_spec(
    project_spec: dict[str, Any],
    user_intent: str,
    *,
    context_package: dict[str, Any] | None = None,
    contractforge_capabilities: dict[str, Any] | None = None,
    provider: ModelProvider,
    options: GenerationOptions | None = None,
) -> EnrichmentResult:
    """Enrich a pre-generation project specification with a model provider."""

    return _enrich(
        prompt_name="project.spec.enrichment.v1",
        variables={
            "project_spec": project_spec,
            "user_intent": user_intent,
            "context_package": context_package or {},
            "contractforge_capabilities": contractforge_capabilities or _default_contractforge_capabilities(),
        },
        provider=provider,
        options=options,
        deterministic_fallback=project_spec,
    )


def enrich_project_synthesis(
    *,
    context_package: dict[str, Any],
    generated_project: dict[str, Any],
    user_intent: str,
    provider: ModelProvider,
    options: GenerationOptions | None = None,
) -> EnrichmentResult:
    """Enrich a generated project scaffold with context-aware advisory guidance."""

    return _enrich(
        prompt_name="project.synthesis.enrichment.v1",
        variables={
            "context_package": redact_secrets(context_package),
            "generated_project": generated_project,
            "user_intent": user_intent,
        },
        provider=provider,
        options=options,
        deterministic_fallback=generated_project,
    )


def _default_contractforge_capabilities() -> dict[str, Any]:
    return {
        "project_targets": list(supported_project_targets()),
        "write_modes": [
            "append",
            "overwrite",
            "upsert",
            "hash_diff_upsert",
            "historical",
            "snapshot_reconcile_soft_delete",
        ],
        "transforms": ["transform.shape.parse_json", "transform.shape.flatten", "transform.shape.explode", "transform.shape.columns"],
        "contracts": ["ingestion", "annotations", "operations", "access"],
        "review_boundary": [
            "business keys require review",
            "owner/SLA require review",
            "credentials must use secret references",
        ],
    }


def enrich_control_table_analysis(
    deterministic_analysis: dict[str, Any],
    control_table_evidence: dict[str, Any],
    *,
    provider: ModelProvider,
    options: GenerationOptions | None = None,
) -> EnrichmentResult:
    """Enrich deterministic operational analysis with provider-backed guidance."""

    return _enrich(
        prompt_name="observability.enrichment.v1",
        variables={
            "deterministic_analysis": deterministic_analysis,
            "control_table_evidence": redact_secrets(control_table_evidence),
        },
        provider=provider,
        options=options,
        deterministic_fallback=deterministic_analysis,
    )


def _enrich(
    *,
    prompt_name: str,
    variables: dict[str, Any],
    provider: ModelProvider,
    options: GenerationOptions | None,
    deterministic_fallback: dict[str, Any],
) -> EnrichmentResult:
    if provider.name == "offline":
        return EnrichmentResult(
            status="SKIPPED",
            prompt=prompt_name,
            provider=provider.name,
            warnings=["No model provider configured; deterministic output was returned without enrichment."],
        )

    system, prompt = render_prompt(prompt_name, variables)
    template_options = _with_response_schema(prompt_name, options)
    try:
        raw_output = provider.complete(prompt, system=system, options=template_options)
    except ProviderExecutionError as exc:
        safe_error = str(redact_secrets(str(exc)))
        return EnrichmentResult(
            status="FAILED",
            prompt=prompt_name,
            provider=provider.name,
            warnings=[safe_error],
        )

    validation = validate_model_output(raw_output, prompt=prompt_name, deterministic_fallback=deterministic_fallback)
    if validation.status == "FAIL":
        repair = _repair_output(
            prompt_name=prompt_name,
            provider=provider,
            invalid_output=raw_output,
            findings=[f"{finding.code} at {finding.path}: {finding.message}" for finding in validation.findings],
            options=template_options,
            deterministic_fallback=deterministic_fallback,
        )
        if repair.status == "ENRICHED":
            return repair
        return EnrichmentResult(
            status="FAILED",
            prompt=prompt_name,
            provider=provider.name,
            warnings=[
                f"{finding.code} at {finding.path}: {finding.message}"
                for finding in validation.findings
            ],
        )

    boundary_warnings = _deterministic_boundary_warnings(validation.data or {})
    if boundary_warnings:
        return EnrichmentResult(
            status="FAILED",
            prompt=prompt_name,
            provider=provider.name,
            warnings=boundary_warnings,
        )

    return EnrichmentResult(
        status="ENRICHED",
        prompt=prompt_name,
        provider=provider.name,
        data=validation.data,
    )


def _repair_output(
    *,
    prompt_name: str,
    provider: ModelProvider,
    invalid_output: str,
    findings: list[str],
    options: GenerationOptions,
    deterministic_fallback: dict[str, Any],
) -> EnrichmentResult:
    system = (
        "You repair invalid model output for ContractForge AI. "
        "Return only one JSON object that matches the requested schema. "
        "Do not add markdown, prose or wrapper fields."
    )
    prompt = (
        "The previous model output did not match the required schema.\n\n"
        "<validation_findings>\n"
        + "\n".join(f"- {finding}" for finding in findings)
        + "\n</validation_findings>\n\n"
        "<invalid_output>\n"
        f"{invalid_output}\n"
        "</invalid_output>\n\n"
        "Repair the output into the required schema. Convert nested assumption, evidence, decision and "
        "recommendation objects into concise strings. Preserve the review boundary and do not invent facts."
    )
    try:
        raw_repair = provider.complete(prompt, system=system, options=options)
    except ProviderExecutionError as exc:
        safe_error = str(redact_secrets(str(exc)))
        return EnrichmentResult(
            status="FAILED",
            prompt=prompt_name,
            provider=provider.name,
            warnings=[*findings, f"structured_output.repair_failed: {safe_error}"],
        )

    validation = validate_model_output(raw_repair, prompt=prompt_name, deterministic_fallback=deterministic_fallback)
    if validation.status == "FAIL":
        return EnrichmentResult(
            status="FAILED",
            prompt=prompt_name,
            provider=provider.name,
            warnings=[
                *findings,
                *[f"structured_output.repair_failed: {finding.code} at {finding.path}: {finding.message}" for finding in validation.findings],
            ],
        )
    boundary_warnings = _deterministic_boundary_warnings(validation.data or {})
    if boundary_warnings:
        return EnrichmentResult(
            status="FAILED",
            prompt=prompt_name,
            provider=provider.name,
            warnings=[*findings, *boundary_warnings],
        )

    return EnrichmentResult(
        status="ENRICHED",
        prompt=prompt_name,
        provider=provider.name,
        data=validation.data,
        warnings=["Initial provider output failed schema validation and was repaired successfully."],
    )


def _with_response_schema(prompt_name: str, options: GenerationOptions | None) -> GenerationOptions:
    from contractforge_ai.evaluation.prompts import get_prompt_template

    if prompt_name == "project.spec.enrichment.v1":
        if options is None:
            return GenerationOptions()
        return replace(options, response_schema=None, response_schema_name=None)

    template = get_prompt_template(prompt_name)
    schema_name = prompt_name.replace(".", "_").replace("-", "_")
    if options is None:
        return GenerationOptions(response_schema=template.output_schema, response_schema_name=schema_name)
    return replace(
        options,
        response_schema=options.response_schema or template.output_schema,
        response_schema_name=options.response_schema_name or schema_name,
    )


def _deterministic_boundary_warnings(data: dict[str, Any]) -> list[str]:
    """Reject provider attempts to set deterministic status/control fields."""

    warnings: list[str] = []
    for key in sorted(set(data) & PROTECTED_DETERMINISTIC_FIELDS):
        warnings.append(
            f"provider_boundary.protected_field: provider output cannot set deterministic field {key!r}."
        )

    field_updates = data.get("field_updates")
    if isinstance(field_updates, dict):
        for key in sorted(set(field_updates) & PROTECTED_DETERMINISTIC_FIELDS):
            warnings.append(
                f"provider_boundary.protected_field: provider field_updates cannot set deterministic field {key!r}."
            )
    return warnings
