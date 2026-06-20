"""Second-pass critique and confidence scoring for AI-assisted output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_ai.validation import DeterministicValidationReport

CritiqueStatus = Literal["READY", "NEEDS_DECISIONS", "INVALID", "UNSAFE"]
CritiqueSeverity = Literal["low", "medium", "high", "critical"]

PRODUCTION_READY_RE = re.compile(r"\b(production[- ]ready|ready to deploy|safe to deploy|fully validated|approved)\b", re.IGNORECASE)
RISK_TERMS = ("risk", "unsafe", "invalid", "failed", "failure", "missing", "required", "decision")


@dataclass(frozen=True)
class CritiqueFinding:
    """One second-pass critique finding."""

    code: str
    severity: CritiqueSeverity
    message: str
    path: str | None = None
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class CritiqueReport:
    """Critique result that can downgrade generated or enriched output."""

    status: CritiqueStatus
    confidence: float
    evidence_coverage: float
    summary: str
    findings: list[CritiqueFinding] = field(default_factory=list)
    decisions_required: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "READY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "confidence": self.confidence,
            "evidence_coverage": self.evidence_coverage,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
            "decisions_required": self.decisions_required,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Critique Report",
            "",
            f"- Status: `{self.status}`",
            f"- Confidence: `{self.confidence:.2f}`",
            f"- Evidence coverage: `{self.evidence_coverage:.2f}`",
            f"- Summary: {self.summary}",
        ]
        if self.findings:
            lines.extend(["", "## Findings"])
            lines.extend(f"- `{item.severity}` `{item.code}`: {item.message}" for item in self.findings)
        if self.decisions_required:
            lines.extend(["", "## Decisions Required"])
            lines.extend(f"- {item}" for item in self.decisions_required)
        return "\n".join(lines).rstrip() + "\n"


def critique_output(
    output: dict[str, Any],
    *,
    validation: DeterministicValidationReport | None = None,
    context_results: list[dict[str, Any]] | None = None,
) -> CritiqueReport:
    """Critique generated or enriched output using deterministic evidence and validation signals."""

    findings: list[CritiqueFinding] = []
    decisions_required = _decisions(output)
    evidence_items = _evidence(output)
    context_items = context_results or []
    evidence_coverage = _evidence_coverage(output, evidence_items, context_items)

    if validation is not None:
        findings.extend(_validation_findings(validation))
        decisions_required.extend(validation.decisions_required)
        if validation.status in {"INVALID", "UNSAFE"} and _claims_ready(output):
            findings.append(
                CritiqueFinding(
                    code="critique.validation_failure_hidden",
                    severity="critical",
                    message="Output claims readiness while deterministic validation is not ready.",
                    recommendation="Preserve validation status and keep the output review-required.",
                )
            )

    if _claims_ready(output) and decisions_required:
        findings.append(
            CritiqueFinding(
                code="critique.ready_claim_with_decisions",
                severity="high",
                message="Output claims readiness while decisions remain open.",
                recommendation="Resolve decisions before marking output ready.",
            )
        )

    if evidence_coverage < 0.35:
        findings.append(
            CritiqueFinding(
                code="critique.evidence_coverage.low",
                severity="high",
                message="Output has low evidence coverage for its recommendations and claims.",
                recommendation="Add cited evidence from deterministic checks, retrieved context or source artifacts.",
            )
        )

    if _has_transform_metadata_mix(output):
        findings.append(
            CritiqueFinding(
                code="critique.boundary.metadata_transform_mix",
                severity="high",
                message="Output appears to mix metadata/governance fields into transformation logic.",
                recommendation="Keep table/column metadata in annotations and transformation logic in transform/shape.",
            )
        )

    status = _status(findings, decisions_required, validation)
    confidence = _confidence(status, evidence_coverage, findings, validation)
    return CritiqueReport(
        status=status,
        confidence=confidence,
        evidence_coverage=round(evidence_coverage, 2),
        summary=_summary(status, findings, decisions_required),
        findings=findings,
        decisions_required=sorted(dict.fromkeys(decisions_required)),
    )


def _validation_findings(validation: DeterministicValidationReport) -> list[CritiqueFinding]:
    if validation.status == "READY":
        return []
    severity: CritiqueSeverity = "critical" if validation.status in {"INVALID", "UNSAFE"} else "high"
    return [
        CritiqueFinding(
            code=f"critique.validation.{validation.status.lower()}",
            severity=severity,
            message=validation.summary,
            recommendation="Do not treat output as ready until deterministic validation passes.",
        )
    ]


def _status(
    findings: list[CritiqueFinding],
    decisions_required: list[str],
    validation: DeterministicValidationReport | None,
) -> CritiqueStatus:
    if validation is not None and validation.status == "UNSAFE":
        return "UNSAFE"
    severities = {finding.severity for finding in findings}
    if "critical" in severities or (validation is not None and validation.status == "INVALID"):
        return "INVALID"
    if {"high", "medium"} & severities or decisions_required or (
        validation is not None and validation.status == "NEEDS_DECISIONS"
    ):
        return "NEEDS_DECISIONS"
    return "READY"


def _confidence(
    status: CritiqueStatus,
    evidence_coverage: float,
    findings: list[CritiqueFinding],
    validation: DeterministicValidationReport | None,
) -> float:
    score = 0.55 + evidence_coverage * 0.35
    if validation is not None and validation.status == "READY":
        score += 0.10
    score -= sum(_penalty(finding.severity) for finding in findings)
    if status == "UNSAFE":
        score = min(score, 0.20)
    elif status == "INVALID":
        score = min(score, 0.40)
    elif status == "NEEDS_DECISIONS":
        score = min(score, 0.72)
    return round(max(0.0, min(score, 0.98)), 2)


def _penalty(severity: CritiqueSeverity) -> float:
    return {"low": 0.03, "medium": 0.08, "high": 0.16, "critical": 0.28}[severity]


def _summary(status: CritiqueStatus, findings: list[CritiqueFinding], decisions_required: list[str]) -> str:
    if status == "READY":
        return "Output passed second-pass critique with sufficient evidence coverage."
    return f"{status}: {len(findings)} critique finding(s) and {len(set(decisions_required))} decision(s) require review."


def _evidence_coverage(
    output: dict[str, Any],
    evidence_items: list[Any],
    context_items: list[dict[str, Any]],
) -> float:
    claims = _claim_count(output)
    if claims == 0:
        return 1.0 if evidence_items or context_items else 0.5
    evidence_count = len(evidence_items) + len(context_items)
    return min(1.0, evidence_count / claims)


def _claim_count(value: Any) -> int:
    if isinstance(value, dict):
        count = 0
        for key, item in value.items():
            if str(key) in {"recommendations", "summary", "assumptions", "decisions_required"}:
                count += _claim_count(item)
            elif isinstance(item, (dict, list)):
                count += _claim_count(item)
        return count
    if isinstance(value, list):
        return sum(_claim_count(item) for item in value)
    if isinstance(value, str):
        return 1 if len(value.strip()) > 15 else 0
    return 0


def _evidence(output: dict[str, Any]) -> list[Any]:
    evidence = output.get("evidence")
    if isinstance(evidence, list):
        return [item for item in evidence if item]
    if isinstance(evidence, dict):
        return [evidence]
    return []


def _decisions(output: dict[str, Any]) -> list[str]:
    decisions = output.get("decisions_required")
    if isinstance(decisions, list):
        return [str(item) for item in decisions if str(item).strip()]
    if decisions:
        return [str(decisions)]
    return []


def _claims_ready(output: dict[str, Any]) -> bool:
    if output.get("review_required") is False and not _decisions(output):
        return True
    text = _flatten_text(output)
    return bool(PRODUCTION_READY_RE.search(text))


def _has_transform_metadata_mix(output: dict[str, Any]) -> bool:
    shape = output.get("shape")
    transform = output.get("transform")
    for value in (shape, transform):
        if not isinstance(value, dict):
            continue
        text = _flatten_text(value).lower()
        if any(term in text for term in ("pii", "owner", "business_owner", "tags", "description")):
            return True
    return False


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_flatten_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    if value is None:
        return ""
    return str(value)
