"""Deterministic provider routing policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from contractforge_ai.providers.capabilities import (
    ProviderCapabilities,
    StructuredOutputStrategy,
    list_provider_capabilities,
)

ProviderTask = Literal[
    "review_enrichment",
    "failure_explanation",
    "metadata_enrichment",
    "project_planning",
]


@dataclass(frozen=True)
class ScoreEffect:
    """One additive provider-routing scoring effect."""

    score: int
    reason: str | None = None
    warning: str | None = None


@dataclass(frozen=True)
class BlockerRule:
    """One declarative provider-routing blocker."""

    predicate: Callable[[ProviderCapabilities, "ProviderRoutingRequest"], bool]
    message: str


@dataclass(frozen=True)
class TaskScoreRule:
    """One declarative task-specific provider-routing score rule."""

    predicate: Callable[[ProviderCapabilities], bool]
    effect: ScoreEffect


STRUCTURED_OUTPUT_EFFECTS: dict[StructuredOutputStrategy, ScoreEffect] = {
    "strict_schema": ScoreEffect(
        score=30,
        reason="Provider supports strict structured-output controls.",
    ),
    "endpoint_dependent": ScoreEffect(
        score=16,
        warning="Structured-output behavior depends on the configured endpoint/model.",
    ),
    "json_mode_only": ScoreEffect(
        score=12,
        warning="Provider supports JSON mode but still requires local schema validation.",
    ),
    "tool_schema": ScoreEffect(
        score=20,
        reason="Provider has a structured-output path suitable for future implementation.",
    ),
    "native_schema": ScoreEffect(
        score=20,
        reason="Provider has a structured-output path suitable for future implementation.",
    ),
    "none": ScoreEffect(
        score=-20,
        warning="Provider has no structured-output controls.",
    ),
}


HTTP_ONLY_PREFERENCE_EFFECTS = {
    "http_only": ScoreEffect(
        score=16,
        reason="Provider can run with HTTP-only dependencies.",
    ),
    "platform_native": ScoreEffect(
        score=8,
        reason="Provider uses Databricks platform-native HTTP boundary.",
    ),
}


DATABRICKS_BOUNDARY_EFFECTS: dict[bool, ScoreEffect] = {
    True: ScoreEffect(
        score=35,
        reason="Provider stays inside the Databricks model-serving boundary.",
    ),
    False: ScoreEffect(
        score=-12,
        warning="Provider is outside the Databricks model-serving boundary.",
    ),
}


BLOCKER_RULES = (
    BlockerRule(
        predicate=lambda provider, request: provider.name == "offline" and not request.include_offline,
        message="Offline provider is excluded from provider-backed routing by default.",
    ),
    BlockerRule(
        predicate=lambda provider, request: bool(request.allowed_providers) and provider.name not in request.allowed_providers,
        message="Provider is not in the allowed provider list.",
    ),
    BlockerRule(
        predicate=lambda provider, request: provider.name in request.excluded_providers,
        message="Provider is explicitly excluded.",
    ),
    BlockerRule(
        predicate=lambda provider, request: provider.status == "planned" and not request.allow_planned,
        message="Provider is registered as planned and cannot be selected unless allow_planned is true.",
    ),
    BlockerRule(
        predicate=lambda provider, request: request.require_strict_schema
        and provider.structured_output_strategy != "strict_schema",
        message="Strict schema was required but the provider does not declare strict schema support.",
    ),
)


TASK_SCORE_RULES: dict[ProviderTask, tuple[TaskScoreRule, ...]] = {
    "project_planning": (
        TaskScoreRule(
            predicate=lambda provider: provider.structured_output_strategy == "strict_schema",
            effect=ScoreEffect(
                score=12,
                reason="Project planning benefits from strict schema because output drives generated artifacts.",
            ),
        ),
        TaskScoreRule(
            predicate=lambda provider: provider.needs_local_validation,
            effect=ScoreEffect(
                score=4,
                warning="Project planning output must remain review-required after local validation.",
            ),
        ),
    ),
    "metadata_enrichment": (
        TaskScoreRule(
            predicate=lambda provider: provider.structured_output_strategy in {"strict_schema", "native_schema", "tool_schema"},
            effect=ScoreEffect(
                score=10,
                reason="Metadata enrichment benefits from structured evidence and recommendation arrays.",
            ),
        ),
        TaskScoreRule(
            predicate=lambda provider: True,
            effect=ScoreEffect(score=3),
        ),
    ),
    "failure_explanation": (
        TaskScoreRule(
            predicate=lambda provider: provider.databricks_dependency_mode == "platform_native",
            effect=ScoreEffect(
                score=10,
                reason="Failure explanation can benefit from Databricks-native operational boundaries.",
            ),
        ),
        TaskScoreRule(
            predicate=lambda provider: provider.databricks_dependency_mode == "http_only",
            effect=ScoreEffect(
                score=7,
                reason="Failure explanation can run without SDK dependencies.",
            ),
        ),
    ),
    "review_enrichment": (
        TaskScoreRule(
            predicate=lambda provider: provider.structured_output_strategy == "strict_schema",
            effect=ScoreEffect(
                score=10,
                reason="Review enrichment benefits from strict finding and recommendation structure.",
            ),
        ),
        TaskScoreRule(
            predicate=lambda provider: provider.structured_output_strategy == "json_mode_only",
            effect=ScoreEffect(
                score=5,
                warning="Review enrichment must rely on local schema validation for this provider.",
            ),
        ),
    ),
}


@dataclass(frozen=True)
class ProviderRoutingRequest:
    """Provider routing constraints for one ContractForge AI task."""

    task: ProviderTask
    require_strict_schema: bool = False
    allow_planned: bool = False
    prefer_http_only: bool = False
    prefer_databricks_boundary: bool = False
    include_offline: bool = False
    allowed_providers: tuple[str, ...] = ()
    excluded_providers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "require_strict_schema": self.require_strict_schema,
            "allow_planned": self.allow_planned,
            "prefer_http_only": self.prefer_http_only,
            "prefer_databricks_boundary": self.prefer_databricks_boundary,
            "include_offline": self.include_offline,
            "allowed_providers": list(self.allowed_providers),
            "excluded_providers": list(self.excluded_providers),
        }


@dataclass(frozen=True)
class ProviderRouteRecommendation:
    """One ranked provider routing recommendation."""

    provider: str
    display_name: str
    status: str
    score: int
    recommended: bool
    structured_output_strategy: StructuredOutputStrategy
    transport_mode: str
    databricks_dependency_mode: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "display_name": self.display_name,
            "status": self.status,
            "score": self.score,
            "recommended": self.recommended,
            "structured_output_strategy": self.structured_output_strategy,
            "transport_mode": self.transport_mode,
            "databricks_dependency_mode": self.databricks_dependency_mode,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "blockers": self.blockers,
        }


@dataclass(frozen=True)
class ProviderRoutingReport:
    """Ranked provider routing report."""

    request: ProviderRoutingRequest
    recommendations: list[ProviderRouteRecommendation]

    @property
    def selected(self) -> ProviderRouteRecommendation | None:
        for recommendation in self.recommendations:
            if recommendation.recommended:
                return recommendation
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "selected": self.selected.to_dict() if self.selected else None,
            "recommendations": [recommendation.to_dict() for recommendation in self.recommendations],
        }

    def to_markdown(self) -> str:
        selected = self.selected.provider if self.selected else "none"
        lines = [
            "# Provider Routing Report",
            "",
            f"- Task: `{self.request.task}`",
            f"- Selected: `{selected}`",
            "",
            "## Recommendations",
        ]
        for item in self.recommendations:
            marker = "recommended" if item.recommended else "not selected"
            lines.extend(
                [
                    "",
                    f"### `{item.provider}`",
                    "",
                    f"- Status: `{item.status}`",
                    f"- Score: `{item.score}`",
                    f"- Result: `{marker}`",
                    f"- Structured output: `{item.structured_output_strategy}`",
                    f"- Transport: `{item.transport_mode}`",
                    f"- Databricks dependency: `{item.databricks_dependency_mode}`",
                ]
            )
            if item.blockers:
                lines.extend(["", "Blockers:"])
                lines.extend(f"- {blocker}" for blocker in item.blockers)
            if item.warnings:
                lines.extend(["", "Warnings:"])
                lines.extend(f"- {warning}" for warning in item.warnings)
            if item.reasons:
                lines.extend(["", "Reasons:"])
                lines.extend(f"- {reason}" for reason in item.reasons)
        return "\n".join(lines).rstrip() + "\n"


def recommend_providers(request: ProviderRoutingRequest) -> ProviderRoutingReport:
    """Rank providers for a ContractForge AI task using declared capabilities."""

    recommendations = [_score_provider(provider, request) for provider in list_provider_capabilities()]
    recommendations = sorted(
        recommendations,
        key=lambda item: (not item.blockers, item.score, item.provider),
        reverse=True,
    )
    if recommendations:
        for index, recommendation in enumerate(recommendations):
            if not recommendation.blockers:
                recommendations[index] = _as_selected(recommendation)
                break
    return ProviderRoutingReport(request=request, recommendations=recommendations)


def _score_provider(provider: ProviderCapabilities, request: ProviderRoutingRequest) -> ProviderRouteRecommendation:
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []
    blockers = _blockers(provider, request)

    if not blockers:
        score += 40
        if provider.implemented:
            score += 25
            reasons.append("Provider has a concrete implementation.")
        score += _apply_score_effect(STRUCTURED_OUTPUT_EFFECTS[provider.structured_output_strategy], reasons, warnings)

        score += _task_score(provider, request.task, reasons, warnings)

        if request.prefer_http_only:
            effect = HTTP_ONLY_PREFERENCE_EFFECTS.get(
                provider.databricks_dependency_mode,
                ScoreEffect(score=-8, warning="Provider may require an SDK or package dependency."),
            )
            score += _apply_score_effect(effect, reasons, warnings)

        if request.prefer_databricks_boundary:
            score += _apply_score_effect(DATABRICKS_BOUNDARY_EFFECTS[provider.name == "databricks"], reasons, warnings)

    return ProviderRouteRecommendation(
        provider=provider.name,
        display_name=provider.display_name,
        status=provider.status,
        score=max(score, 0),
        recommended=False,
        structured_output_strategy=provider.structured_output_strategy,
        transport_mode=provider.transport_mode,
        databricks_dependency_mode=provider.databricks_dependency_mode,
        reasons=reasons,
        warnings=warnings,
        blockers=blockers,
    )


def _blockers(provider: ProviderCapabilities, request: ProviderRoutingRequest) -> list[str]:
    return [rule.message for rule in BLOCKER_RULES if rule.predicate(provider, request)]


def _task_score(
    provider: ProviderCapabilities,
    task: ProviderTask,
    reasons: list[str],
    warnings: list[str],
) -> int:
    for rule in TASK_SCORE_RULES[task]:
        if rule.predicate(provider):
            return _apply_score_effect(rule.effect, reasons, warnings)
    return 0


def _apply_score_effect(effect: ScoreEffect, reasons: list[str], warnings: list[str]) -> int:
    if effect.reason:
        reasons.append(effect.reason)
    if effect.warning:
        warnings.append(effect.warning)
    return effect.score


def _as_selected(recommendation: ProviderRouteRecommendation) -> ProviderRouteRecommendation:
    return ProviderRouteRecommendation(
        provider=recommendation.provider,
        display_name=recommendation.display_name,
        status=recommendation.status,
        score=recommendation.score,
        recommended=True,
        structured_output_strategy=recommendation.structured_output_strategy,
        transport_mode=recommendation.transport_mode,
        databricks_dependency_mode=recommendation.databricks_dependency_mode,
        reasons=recommendation.reasons,
        warnings=recommendation.warnings,
        blockers=recommendation.blockers,
    )
