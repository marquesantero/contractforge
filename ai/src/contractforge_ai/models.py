"""Shared result models for ContractForge AI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Severity = Literal["info", "low", "medium", "high", "critical"]
ConfidenceLevel = Literal["low", "medium", "high"]
ValidationStatus = Literal["PASS", "WARN", "FAIL"]


def confidence_level(score: float) -> ConfidenceLevel:
    """Return a stable confidence bucket for a numeric confidence score."""

    if score >= 0.80:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


@dataclass(frozen=True)
class EvidenceItem:
    """A traceable evidence item used to justify a suggestion or generated artifact."""

    source: str
    reason: str
    path: str | None = None
    value: Any | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}

    def to_markdown(self) -> str:
        path = f" `{self.path}`" if self.path else ""
        value = f" = `{self.value}`" if self.value is not None else ""
        confidence = f" ({confidence_level(self.confidence)})" if self.confidence is not None else ""
        return f"- **{self.source}**{path}{value}: {self.reason}{confidence}"


@dataclass(frozen=True)
class Assumption:
    """An assumption made while producing advisory output."""

    statement: str
    confidence: float = 0.50
    evidence: list[EvidenceItem] = field(default_factory=list)
    review_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "confidence": self.confidence,
            "confidence_level": confidence_level(self.confidence),
            "review_required": self.review_required,
            "evidence": [item.to_dict() for item in self.evidence],
        }

    def to_markdown(self) -> str:
        marker = "review required" if self.review_required else "informational"
        return f"- {self.statement} ({confidence_level(self.confidence)}, {marker})"


@dataclass(frozen=True)
class RequiredDecision:
    """A decision the user must make before treating output as production-ready."""

    question: str
    reason: str
    path: str | None = None
    options: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "question": self.question,
            "reason": self.reason,
            "path": self.path,
            "options": self.options,
        }
        return {key: value for key, value in payload.items() if value not in (None, [])}

    def to_markdown(self) -> str:
        path = f" `{self.path}`" if self.path else ""
        options = f" Options: {', '.join(self.options)}." if self.options else ""
        return f"- {self.question}{path}: {self.reason}.{options}"


@dataclass(frozen=True)
class Traceability:
    """Evidence, confidence, assumptions and decisions attached to advisory output."""

    confidence: float = 1.0
    evidence: list[EvidenceItem] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    decisions_required: list[RequiredDecision] = field(default_factory=list)
    review_required: bool = False

    @property
    def confidence_level(self) -> ConfidenceLevel:
        return confidence_level(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "review_required": self.review_required or bool(self.decisions_required),
            "evidence": [item.to_dict() for item in self.evidence],
            "assumptions": [item.to_dict() for item in self.assumptions],
            "decisions_required": [item.to_dict() for item in self.decisions_required],
        }

    def to_markdown(self) -> str:
        sections = [
            "## Traceability",
            f"- Confidence: **{self.confidence_level}** ({self.confidence:.2f})",
            f"- Review required: **{str(self.review_required or bool(self.decisions_required)).lower()}**",
        ]
        if self.evidence:
            sections.extend(["", "### Evidence", *[item.to_markdown() for item in self.evidence]])
        if self.assumptions:
            sections.extend(["", "### Assumptions", *[item.to_markdown() for item in self.assumptions]])
        if self.decisions_required:
            sections.extend(["", "### Decisions Required", *[item.to_markdown() for item in self.decisions_required]])
        return "\n".join(sections)


@dataclass(frozen=True)
class Finding:
    """A review finding produced by deterministic checks or model enrichment."""

    code: str
    severity: Severity
    title: str
    detail: str
    recommendation: str
    path: str | None = None
    evidence: list[EvidenceItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "recommendation": self.recommendation,
            "path": self.path,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class ReviewResult:
    """Structured review response."""

    status: Literal["PASS", "WARN", "FAIL"]
    risk: Severity
    contract_path: str
    findings: list[Finding] = field(default_factory=list)
    summary: str = ""
    traceability: Traceability = field(default_factory=Traceability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "risk": self.risk,
            "contract_path": self.contract_path,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
            "traceability": self.traceability.to_dict(),
        }


@dataclass(frozen=True)
class FailureExplanation:
    """Structured explanation for a failed ContractForge run."""

    status: Literal["EXPLAINED", "UNKNOWN"]
    primary_category: str
    risk: Severity
    confidence: float
    summary: str
    findings: list[Finding] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    traceability: Traceability = field(default_factory=Traceability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "primary_category": self.primary_category,
            "risk": self.risk,
            "confidence": self.confidence,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
            "recommended_actions": self.recommended_actions,
            "evidence": self.evidence,
            "traceability": self.traceability.to_dict(),
        }


@dataclass(frozen=True)
class Suggestion:
    """A generated suggestion with evidence and confidence."""

    kind: str
    target: str
    value: Any
    confidence: float
    evidence: list[str] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "value": self.value,
            "confidence": self.confidence,
            "confidence_level": confidence_level(self.confidence),
            "review_required": self.review_required or confidence_level(self.confidence) == "low",
            "evidence": self.evidence,
            "evidence_items": [item.to_dict() for item in self.evidence_items],
            "assumptions": [item.to_dict() for item in self.assumptions],
        }


@dataclass(frozen=True)
class MetadataSuggestionResult:
    """Suggested annotations and quality rules."""

    source_path: str
    annotations: dict[str, Any]
    quality_rules: dict[str, Any]
    suggestions: list[Suggestion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    traceability: Traceability = field(default_factory=Traceability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "annotations": self.annotations,
            "quality_rules": self.quality_rules,
            "suggestions": [suggestion.to_dict() for suggestion in self.suggestions],
            "warnings": self.warnings,
            "traceability": self.traceability.to_dict(),
        }


@dataclass(frozen=True)
class ShapeSuggestionResult:
    """Suggested ContractForge shape configuration for nested payloads."""

    source_path: str
    shape: dict[str, Any]
    python_example: str
    decisions_required: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    discovered_paths: list[dict[str, Any]] = field(default_factory=list)
    traceability: Traceability = field(default_factory=Traceability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "shape": self.shape,
            "python_example": self.python_example,
            "decisions_required": self.decisions_required,
            "warnings": self.warnings,
            "discovered_paths": self.discovered_paths,
            "traceability": self.traceability.to_dict(),
        }


@dataclass(frozen=True)
class ValidationResult:
    """Deterministic validation result for generated artifacts."""

    status: ValidationStatus
    summary: str
    findings: list[Finding] = field(default_factory=list)
    traceability: Traceability = field(default_factory=Traceability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
            "traceability": self.traceability.to_dict(),
        }


@dataclass(frozen=True)
class ContractDraftResult:
    """Generated draft ContractForge contract."""

    source_path: str
    contract: dict[str, Any]
    assumptions: list[str] = field(default_factory=list)
    decisions_required: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    traceability: Traceability = field(default_factory=Traceability)
    validation: ValidationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "source_path": self.source_path,
            "contract": self.contract,
            "assumptions": self.assumptions,
            "decisions_required": self.decisions_required,
            "warnings": self.warnings,
            "traceability": self.traceability.to_dict(),
        }
        if self.validation is not None:
            payload["validation"] = self.validation.to_dict()
        return payload
