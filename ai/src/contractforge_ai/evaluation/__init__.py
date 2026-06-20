"""Evaluation utilities for prompt and AI-enrichment safety."""

from contractforge_ai.evaluation.prompts import (
    PromptEvalCase,
    PromptEvalFinding,
    PromptEvalResult,
    PromptTemplateSpec,
    evaluate_prompt_cases,
    get_prompt_template,
    list_prompt_templates,
    render_prompt,
)
from contractforge_ai.evaluation.provider_live import (
    DEFAULT_PROVIDER_EVAL_PROMPTS,
    ProviderEvalFinding,
    ProviderEvaluationReport,
    ProviderPromptEvaluation,
    evaluate_provider,
)
from contractforge_ai.evaluation.enrichment_quality import (
    EnrichmentQualityFinding,
    EnrichmentQualityReport,
    evaluate_enrichment_quality,
    load_json_payload,
)
from contractforge_ai.evaluation.structured import (
    StructuredOutputFinding,
    StructuredOutputValidation,
    validate_model_output,
)

__all__ = [
    "PromptEvalCase",
    "PromptEvalFinding",
    "PromptEvalResult",
    "PromptTemplateSpec",
    "DEFAULT_PROVIDER_EVAL_PROMPTS",
    "EnrichmentQualityFinding",
    "EnrichmentQualityReport",
    "ProviderEvalFinding",
    "ProviderEvaluationReport",
    "ProviderPromptEvaluation",
    "StructuredOutputFinding",
    "StructuredOutputValidation",
    "evaluate_enrichment_quality",
    "evaluate_provider",
    "evaluate_prompt_cases",
    "get_prompt_template",
    "list_prompt_templates",
    "load_json_payload",
    "render_prompt",
    "validate_model_output",
]
