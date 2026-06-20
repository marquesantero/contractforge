"""Task routing and prompt orchestration for context-aware AI workflows."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_ai.context import KnowledgeIndex, KnowledgeSearchResult, query_knowledge_index
from contractforge_ai.providers import ProviderRoutingRequest, recommend_providers

IntelligenceTask = Literal[
    "contract_review",
    "failure_explanation",
    "metadata_suggestion",
    "shape_suggestion",
    "project_planning",
    "project_synthesis",
    "observability_analysis",
]


@dataclass(frozen=True)
class TaskRouteSpec:
    """Routing metadata for one high-level ContractForge AI task."""

    task: IntelligenceTask
    prompt_name: str | None
    provider_task: str
    description: str
    keywords: tuple[str, ...]
    required_inputs: tuple[str, ...]
    context_queries: tuple[str, ...]
    require_strict_schema: bool = False
    prefer_databricks_boundary: bool = False


@dataclass(frozen=True)
class TaskRouteRequest:
    """Input used to infer the best AI workflow for a user request."""

    intent: str
    task_hint: IntelligenceTask | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    knowledge_index: KnowledgeIndex | None = None
    context_limit: int = 5
    prefer_http_only: bool = False
    prefer_databricks_boundary: bool = False
    require_strict_schema: bool | None = None


@dataclass(frozen=True)
class TaskRoutingReport:
    """Auditable task-routing result with optional local knowledge context."""

    task: IntelligenceTask
    prompt_name: str | None
    provider_task: str
    confidence: float
    description: str
    required_inputs: tuple[str, ...]
    context_queries: tuple[str, ...]
    context_results: tuple[KnowledgeSearchResult, ...]
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    provider_routing: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "prompt_name": self.prompt_name,
            "provider_task": self.provider_task,
            "confidence": self.confidence,
            "description": self.description,
            "required_inputs": list(self.required_inputs),
            "context_queries": list(self.context_queries),
            "context_results": [result.to_dict() for result in self.context_results],
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "provider_routing": self.provider_routing,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Task Routing Report",
            "",
            f"- Task: `{self.task}`",
            f"- Prompt: `{self.prompt_name or 'none'}`",
            f"- Provider task: `{self.provider_task}`",
            f"- Confidence: `{self.confidence:.2f}`",
            "",
            "## Required Inputs",
            *[f"- `{item}`" for item in self.required_inputs],
            "",
            "## Reasons",
            *[f"- {item}" for item in self.reasons],
        ]
        if self.warnings:
            lines.extend(["", "## Warnings", *[f"- {item}" for item in self.warnings]])
        if self.context_results:
            lines.extend(["", "## Retrieved Context"])
            lines.extend(
                f"- `{item.source_path}:{item.start_line}-{item.end_line}` score `{item.score}`"
                for item in self.context_results
            )
        return "\n".join(lines).rstrip() + "\n"


TASK_ROUTE_SPECS: dict[IntelligenceTask, TaskRouteSpec] = {
    "contract_review": TaskRouteSpec(
        task="contract_review",
        prompt_name="review.enrichment.v1",
        provider_task="review_enrichment",
        description="Review an existing ContractForge contract or bundle.",
        keywords=("review", "validate", "contract", "ingestion.yaml", "bundle", "finding", "risk"),
        required_inputs=("contract_path",),
        context_queries=("contract review quality gates write modes", "ContractForge split contracts validation"),
    ),
    "failure_explanation": TaskRouteSpec(
        task="failure_explanation",
        prompt_name="explain.enrichment.v1",
        provider_task="failure_explanation",
        description="Explain a failed run using run/error evidence.",
        keywords=("failed", "failure", "error", "traceback", "run_id", "ctrl_ingestion_errors", "exception"),
        required_inputs=("run_evidence",),
        context_queries=("ContractForge failure categories control tables", "Databricks connector runtime errors"),
        prefer_databricks_boundary=True,
    ),
    "metadata_suggestion": TaskRouteSpec(
        task="metadata_suggestion",
        prompt_name="metadata.enrichment.v1",
        provider_task="metadata_enrichment",
        description="Suggest annotations, quality rules and governance metadata.",
        keywords=("annotations", "metadata", "pii", "quality", "required", "description", "tags", "owner"),
        required_inputs=("schema_profile",),
        context_queries=("annotations yaml pii tags quality rules", "ContractForge data contract metadata"),
    ),
    "shape_suggestion": TaskRouteSpec(
        task="shape_suggestion",
        prompt_name=None,
        provider_task="metadata_enrichment",
        description="Suggest transform.shape configuration from nested samples.",
        keywords=("shape", "flatten", "explode", "json", "array", "struct", "transform", "parse_json"),
        required_inputs=("sample_payload",),
        context_queries=("transform shape flatten arrays parse_json", "ContractForge nested JSON transformation"),
    ),
    "project_planning": TaskRouteSpec(
        task="project_planning",
        prompt_name="project.plan.enrichment.v1",
        provider_task="project_planning",
        description="Plan a ContractForge project before writing files.",
        keywords=("plan", "project", "generate", "dab", "dbt", "classic", "scaffold", "requirements"),
        required_inputs=("user_intent",),
        context_queries=("project planning generated contracts Databricks Asset Bundle", "ContractForge project templates"),
        require_strict_schema=True,
    ),
    "project_synthesis": TaskRouteSpec(
        task="project_synthesis",
        prompt_name="project.synthesis.enrichment.v1",
        provider_task="project_planning",
        description="Review and improve a generated project scaffold with local context.",
        keywords=("complete project", "generated project", "synthesis", "context package", "write files", "scaffold"),
        required_inputs=("context_package", "generated_project", "user_intent"),
        context_queries=("context aware generated project decisions", "ContractForge project scaffold review"),
        require_strict_schema=True,
    ),
    "observability_analysis": TaskRouteSpec(
        task="observability_analysis",
        prompt_name="observability.enrichment.v1",
        provider_task="failure_explanation",
        description="Analyze control-table evidence across many runs.",
        keywords=("control tables", "dashboard", "observability", "ctrl_", "sla", "failure rate", "quality trend"),
        required_inputs=("control_table_evidence",),
        context_queries=("control tables observability operational recommendations", "ContractForge dashboard metrics"),
        prefer_databricks_boundary=True,
    ),
}


def route_task(request: TaskRouteRequest) -> TaskRoutingReport:
    """Infer the best task, prompt and context retrieval plan for a ContractForge AI request."""

    selected_task, confidence, reasons = _select_task(request)
    spec = TASK_ROUTE_SPECS[selected_task]
    context_queries = _context_queries(spec, request.intent)
    context_results = _retrieve_context(request.knowledge_index, context_queries, request.context_limit)
    warnings = _warnings(request, confidence, context_results)
    provider_request = ProviderRoutingRequest(
        task=spec.provider_task,  # type: ignore[arg-type]
        require_strict_schema=spec.require_strict_schema
        if request.require_strict_schema is None
        else request.require_strict_schema,
        prefer_http_only=request.prefer_http_only,
        prefer_databricks_boundary=spec.prefer_databricks_boundary or request.prefer_databricks_boundary,
    )
    return TaskRoutingReport(
        task=spec.task,
        prompt_name=spec.prompt_name,
        provider_task=spec.provider_task,
        confidence=confidence,
        description=spec.description,
        required_inputs=spec.required_inputs,
        context_queries=context_queries,
        context_results=context_results,
        reasons=reasons,
        warnings=warnings,
        provider_routing=recommend_providers(provider_request).to_dict(),
    )


def _select_task(request: TaskRouteRequest) -> tuple[IntelligenceTask, float, tuple[str, ...]]:
    if request.task_hint is not None:
        return request.task_hint, 0.95, (f"Explicit task hint selected `{request.task_hint}`.",)

    text = _routing_text(request)
    scored = sorted(
        (_score_spec(spec, text) for spec in TASK_ROUTE_SPECS.values()),
        key=lambda item: (item[0], item[1].task),
        reverse=True,
    )
    score, spec, matched = scored[0]
    if score == 0:
        return (
            "project_planning",
            0.35,
            ("No specific task signal was strong enough; defaulted to project planning for safe review.",),
        )
    confidence = min(0.95, 0.45 + (score / max(len(spec.keywords), 1)) * 0.5)
    reasons = tuple(f"Matched `{term}` for `{spec.task}`." for term in matched[:5])
    return spec.task, round(confidence, 2), reasons


def _score_spec(spec: TaskRouteSpec, text: str) -> tuple[int, TaskRouteSpec, tuple[str, ...]]:
    tokens = Counter(_tokens(text))
    phrase_hits = tuple(keyword for keyword in spec.keywords if " " in keyword and keyword in text)
    token_hits = tuple(keyword for keyword in spec.keywords if " " not in keyword and tokens.get(keyword, 0) > 0)
    return len(phrase_hits) * 2 + len(token_hits), spec, (*phrase_hits, *token_hits)


def _routing_text(request: TaskRouteRequest) -> str:
    artifact_text = " ".join(str(value) for value in request.artifacts.values())
    return f"{request.intent} {artifact_text}".lower()


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[a-zA-Z0-9_]+", text)]


def _context_queries(spec: TaskRouteSpec, intent: str) -> tuple[str, ...]:
    compact_intent = re.sub(r"\s+", " ", intent).strip()
    queries = [compact_intent, *spec.context_queries] if compact_intent else list(spec.context_queries)
    return tuple(dict.fromkeys(queries))


def _retrieve_context(
    index: KnowledgeIndex | None,
    queries: tuple[str, ...],
    limit: int,
) -> tuple[KnowledgeSearchResult, ...]:
    if index is None or limit <= 0:
        return ()
    selected: dict[str, KnowledgeSearchResult] = {}
    for query in queries:
        for result in query_knowledge_index(index, query, limit=limit):
            current = selected.get(result.chunk_id)
            if current is None or result.score > current.score:
                selected[result.chunk_id] = result
    return tuple(sorted(selected.values(), key=lambda item: (-item.score, item.source_path, item.start_line))[:limit])


def _warnings(
    request: TaskRouteRequest,
    confidence: float,
    context_results: tuple[KnowledgeSearchResult, ...],
) -> tuple[str, ...]:
    warnings = []
    if confidence < 0.6:
        warnings.append("Task confidence is low; ask for clarification before executing a generated plan.")
    if request.knowledge_index is not None and not context_results:
        warnings.append("A knowledge index was provided, but no relevant context was retrieved.")
    return tuple(warnings)
