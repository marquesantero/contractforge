"""Live provider evaluation harness."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from contractforge_ai.evaluation.enrichment_quality import EnrichmentQualityReport, evaluate_enrichment_quality
from contractforge_ai.evaluation.prompts import get_prompt_template, render_prompt
from contractforge_ai.evaluation.structured import StructuredOutputFinding, validate_model_output
from contractforge_ai.providers import (
    GenerationOptions,
    ModelProvider,
    ProviderExecutionError,
    get_provider_capabilities,
)

ProviderEvalStatus = Literal["PASS", "WARN", "FAIL", "SKIPPED"]
ProviderEvalSeverity = Literal["medium", "high", "critical"]


@dataclass(frozen=True)
class ProviderEvalFinding:
    """One finding emitted by live provider evaluation."""

    code: str
    message: str
    severity: ProviderEvalSeverity = "high"
    prompt: str | None = None
    path: str = "$"

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "severity": self.severity,
            "prompt": self.prompt,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class ProviderPromptEvaluation:
    """Evaluation result for one prompt template against one provider."""

    prompt: str
    status: ProviderEvalStatus
    latency_ms: int | None = None
    structured_output_status: str | None = None
    enrichment_quality_status: str | None = None
    findings: list[ProviderEvalFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "structured_output_status": self.structured_output_status,
            "enrichment_quality_status": self.enrichment_quality_status,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class ProviderEvaluationReport:
    """Live provider evaluation report."""

    provider: str
    status: ProviderEvalStatus
    capability: dict[str, Any] | None
    prompt_results: list[ProviderPromptEvaluation]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "capability": self.capability,
            "summary": self.summary,
            "prompt_results": [result.to_dict() for result in self.prompt_results],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Provider Evaluation Report",
            "",
            f"- Provider: `{self.provider}`",
            f"- Status: `{self.status}`",
            f"- Summary: {self.summary}",
        ]
        if self.capability:
            lines.extend(
                [
                    "",
                    "## Capability",
                    "",
                    f"- Structured output: `{self.capability['structured_output_strategy']}`",
                    f"- Transport: `{self.capability['transport_mode']}`",
                    f"- Databricks dependency: `{self.capability['databricks_dependency_mode']}`",
                    f"- Needs local validation: `{self.capability['needs_local_validation']}`",
                ]
            )
        lines.extend(["", "## Prompt Results"])
        for result in self.prompt_results:
            latency = f"{result.latency_ms} ms" if result.latency_ms is not None else "n/a"
            lines.extend(
                [
                    "",
                    f"### `{result.prompt}`",
                    "",
                    f"- Status: `{result.status}`",
                    f"- Latency: `{latency}`",
                    f"- Structured output: `{result.structured_output_status or 'n/a'}`",
                    f"- Enrichment quality: `{result.enrichment_quality_status or 'n/a'}`",
                ]
            )
            if result.findings:
                lines.extend(["", "Findings:"])
                lines.extend(
                    f"- `{finding.code}` ({finding.severity}) at `{finding.path}`: {finding.message}"
                    for finding in result.findings
                )
        return "\n".join(lines).rstrip() + "\n"


DEFAULT_PROVIDER_EVAL_PROMPTS: tuple[str, ...] = (
    "review.enrichment.v1",
    "explain.enrichment.v1",
    "project.plan.enrichment.v1",
)


def evaluate_provider(
    provider: ModelProvider,
    *,
    prompts: list[str] | None = None,
    options: GenerationOptions | None = None,
) -> ProviderEvaluationReport:
    """Evaluate a configured provider against registered prompt templates."""

    selected_prompts = prompts or list(DEFAULT_PROVIDER_EVAL_PROMPTS)
    capability = _provider_capability(provider.name)

    if provider.name == "offline":
        result = ProviderPromptEvaluation(
            prompt="*",
            status="SKIPPED",
            findings=[
                ProviderEvalFinding(
                    code="provider.offline",
                    message="Offline provider does not perform model calls; live provider evaluation was skipped.",
                    severity="medium",
                )
            ],
        )
        return ProviderEvaluationReport(
            provider=provider.name,
            status="SKIPPED",
            capability=capability,
            prompt_results=[result],
            summary="Offline provider skipped live evaluation.",
        )

    results = [_evaluate_prompt(provider, prompt_name, options=options) for prompt_name in selected_prompts]
    status = _overall_status(results)
    return ProviderEvaluationReport(
        provider=provider.name,
        status=status,
        capability=capability,
        prompt_results=results,
        summary=_summary(status, results),
    )


def _evaluate_prompt(
    provider: ModelProvider,
    prompt_name: str,
    *,
    options: GenerationOptions | None,
) -> ProviderPromptEvaluation:
    variables = _default_variables(prompt_name)
    system, prompt = render_prompt(prompt_name, variables)
    call_options = _with_response_schema(prompt_name, options)
    started = time.perf_counter()
    try:
        raw_output = provider.complete(prompt, system=system, options=call_options)
    except ProviderExecutionError as exc:
        return ProviderPromptEvaluation(
            prompt=prompt_name,
            status="FAIL",
            latency_ms=_elapsed_ms(started),
            findings=[
                ProviderEvalFinding(
                    code="provider.execution_failed",
                    message=str(exc),
                    severity="critical",
                    prompt=prompt_name,
                )
            ],
        )

    latency_ms = _elapsed_ms(started)
    validation = validate_model_output(raw_output, prompt=prompt_name, deterministic_fallback=variables)
    findings = [_structured_finding(prompt_name, finding) for finding in validation.findings]
    quality: EnrichmentQualityReport | None = None
    if validation.status == "PASS" and validation.data is not None:
        kind = _prompt_kind(prompt_name)
        quality = evaluate_enrichment_quality(
            _deterministic_baseline(prompt_name, variables),
            {
                "status": "ENRICHED",
                "provider": provider.name,
                "data": validation.data,
            },
            expected_kind=kind,
        )
        findings.extend(_quality_findings(prompt_name, quality))

    status: ProviderEvalStatus = "FAIL" if findings else "PASS"
    return ProviderPromptEvaluation(
        prompt=prompt_name,
        status=status,
        latency_ms=latency_ms,
        structured_output_status=validation.status,
        enrichment_quality_status=quality.status if quality else None,
        findings=findings,
    )


def _provider_capability(provider_name: str) -> dict[str, Any] | None:
    try:
        return get_provider_capabilities(provider_name).to_dict()
    except Exception:
        return None


def _with_response_schema(prompt_name: str, options: GenerationOptions | None) -> GenerationOptions:
    template = get_prompt_template(prompt_name)
    schema_name = prompt_name.replace(".", "_").replace("-", "_")
    if options is None:
        return GenerationOptions(response_schema=template.output_schema, response_schema_name=schema_name)
    return replace(
        options,
        response_schema=options.response_schema or template.output_schema,
        response_schema_name=options.response_schema_name or schema_name,
    )


def _default_variables(prompt_name: str) -> dict[str, Any]:
    if prompt_name == "review.enrichment.v1":
        return {
            "deterministic_result": {
                "status": "WARN",
                "risk": "medium",
                "findings": [{"code": "merge_keys.missing_quality", "severity": "high"}],
                "decisions_required": ["Confirm merge keys and null-key behavior."],
            },
            "contract_excerpt": {
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
                "mode": "hash_diff_upsert",
                "merge_keys": ["order_id"],
            },
        }
    if prompt_name == "explain.enrichment.v1":
        return {
            "deterministic_explanation": {
                "status": "EXPLAINED",
                "primary_category": "network_or_egress",
                "confidence": 0.86,
                "recommended_actions": ["Check workspace egress and DNS/network policy."],
            },
            "redacted_evidence": {
                "error_message": "Temporary failure in name resolution for external API.",
                "run_id": "example-run",
            },
        }
    if prompt_name == "metadata.enrichment.v1":
        return {
            "deterministic_suggestions": {
                "annotations": {"columns": {"customer_email": {"pii": {"enabled": True, "type": "email"}}}},
                "quality_rules": {"not_null": ["customer_id"]},
            },
            "schema_profile": {
                "columns": [
                    {"name": "customer_id", "type": "STRING", "null_count": 0},
                    {"name": "customer_email", "type": "STRING", "sample": "user@example.com"},
                ]
            },
        }
    if prompt_name == "project.plan.enrichment.v1":
        return {
            "project_plan": {
                "status": "NEEDS_DECISIONS",
                "recommendations": [{"target": "contractforge-yaml", "reason": "Best review artifact."}],
                "decisions_required": ["Confirm merge keys.", "Confirm owner."],
            },
            "user_intent": (
                "Create a silver ingestion from s3a://landing/orders into main.silver.orders "
                "using hash_diff_upsert."
            ),
        }
    if prompt_name == "adapter.validation.enrichment.v1":
        return {
            "adapter_validation": {
                "status": "NEEDS_DECISIONS",
                "checks": [
                    {
                        "kind": "adapter",
                        "name": "aws",
                        "status": "NEEDS_DECISIONS",
                        "summary": "AWS adapter planning returned SUPPORTED_WITH_WARNINGS.",
                    }
                ],
                "decisions_required": ["Review AWS hash-diff performance warning before deployment."],
            },
            "project_context": {
                "project": "orders-medallion",
                "adapters": ["databricks", "aws"],
            },
            "user_intent": "Validate generated contracts for Databricks and AWS.",
        }
    template = get_prompt_template(prompt_name)
    raise ValueError(f"No default provider evaluation variables are registered for {template.name!r}.")


def _deterministic_baseline(prompt_name: str, variables: dict[str, Any]) -> dict[str, Any]:
    if prompt_name == "review.enrichment.v1":
        return variables["deterministic_result"]
    if prompt_name == "explain.enrichment.v1":
        return variables["deterministic_explanation"]
    if prompt_name == "metadata.enrichment.v1":
        return variables["deterministic_suggestions"]
    if prompt_name == "project.plan.enrichment.v1":
        return variables["project_plan"]
    if prompt_name == "adapter.validation.enrichment.v1":
        return variables["adapter_validation"]
    return variables


def _prompt_kind(prompt_name: str) -> str:
    schema = get_prompt_template(prompt_name).output_schema
    return str(schema.get("properties", {}).get("kind", {}).get("const", ""))


def _structured_finding(prompt_name: str, finding: StructuredOutputFinding) -> ProviderEvalFinding:
    return ProviderEvalFinding(
        code=finding.code,
        message=finding.message,
        severity=finding.severity,
        prompt=prompt_name,
        path=finding.path,
    )


def _quality_findings(prompt_name: str, quality: EnrichmentQualityReport) -> list[ProviderEvalFinding]:
    return [
        ProviderEvalFinding(
            code=finding.code,
            message=finding.message,
            severity=finding.severity,
            prompt=prompt_name,
            path=finding.path,
        )
        for finding in quality.findings
    ]


def _overall_status(results: list[ProviderPromptEvaluation]) -> ProviderEvalStatus:
    if any(result.status == "FAIL" for result in results):
        return "FAIL"
    if all(result.status == "SKIPPED" for result in results):
        return "SKIPPED"
    if any(result.status == "WARN" for result in results):
        return "WARN"
    return "PASS"


def _summary(status: ProviderEvalStatus, results: list[ProviderPromptEvaluation]) -> str:
    passed = sum(1 for result in results if result.status == "PASS")
    failed = sum(1 for result in results if result.status == "FAIL")
    if status == "PASS":
        return f"Provider passed {passed} prompt evaluation(s)."
    if status == "FAIL":
        return f"Provider failed {failed} prompt evaluation(s); deterministic outputs remain authoritative."
    if status == "SKIPPED":
        return "Provider evaluation was skipped."
    return "Provider evaluation completed with warnings."


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))
