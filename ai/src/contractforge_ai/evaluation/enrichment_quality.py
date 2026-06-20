"""Deterministic quality evaluation for provider enrichment outputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_ai.context.redaction import redact_secrets

EnrichmentQualityStatus = Literal["PASS", "WARN", "FAIL"]
EnrichmentQualitySeverity = Literal["medium", "high", "critical"]


@dataclass(frozen=True)
class EnrichmentQualityFinding:
    """One deterministic quality finding for an enrichment output."""

    code: str
    message: str
    severity: EnrichmentQualitySeverity = "high"
    path: str = "$"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class EnrichmentQualityReport:
    """Quality report comparing enrichment output to deterministic baseline."""

    status: EnrichmentQualityStatus
    score: float
    summary: str
    findings: list[EnrichmentQualityFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Enrichment Quality Report",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score:.2f}`",
            f"- Summary: {self.summary}",
        ]
        if self.findings:
            lines.extend(["", "## Findings"])
            lines.extend(
                f"- `{finding.code}` ({finding.severity}) at `{finding.path}`: {finding.message}"
                for finding in self.findings
            )
        return "\n".join(lines).rstrip() + "\n"


def evaluate_enrichment_quality(
    deterministic_result: dict[str, Any],
    enrichment_payload: dict[str, Any],
    *,
    expected_kind: str | None = None,
) -> EnrichmentQualityReport:
    """Evaluate whether enrichment preserves deterministic review boundaries."""

    enrichment = _extract_enrichment(enrichment_payload)
    findings: list[EnrichmentQualityFinding] = []
    if enrichment is None:
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.missing",
                message="No ai_enrichment payload was found.",
                severity="critical",
            )
        )
        return _report(findings)

    status = enrichment.get("status")
    if status == "SKIPPED":
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.skipped",
                message="Provider enrichment was skipped; deterministic output remains authoritative.",
                severity="medium",
            )
        )
        return _report(findings)
    if status == "FAILED":
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.failed",
                message="Provider enrichment failed validation or execution.",
                severity="high",
            )
        )
        return _report(findings)
    if status != "ENRICHED":
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.invalid_status",
                message="Enrichment status must be ENRICHED, SKIPPED or FAILED.",
                severity="critical",
                path="$.status",
            )
        )
        return _report(findings)

    data = enrichment.get("data")
    if not isinstance(data, dict):
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.data_missing",
                message="ENRICHED payload must contain a data object.",
                severity="critical",
                path="$.data",
            )
        )
        return _report(findings)

    findings.extend(_schema_findings(data, expected_kind=expected_kind))
    findings.extend(_boundary_findings(deterministic_result, data))
    findings.extend(_secret_findings(data))
    return _report(findings)


def _extract_enrichment(payload: dict[str, Any]) -> dict[str, Any] | None:
    if "ai_enrichment" in payload and isinstance(payload["ai_enrichment"], dict):
        return payload["ai_enrichment"]
    if "status" in payload and "provider" in payload:
        return payload
    return None


def _schema_findings(data: dict[str, Any], *, expected_kind: str | None) -> list[EnrichmentQualityFinding]:
    findings: list[EnrichmentQualityFinding] = []
    kind = data.get("kind")
    if expected_kind and kind != expected_kind:
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.kind_mismatch",
                message=f"Expected enrichment kind {expected_kind!r}, got {kind!r}.",
                severity="critical",
                path="$.data.kind",
            )
        )
    if not isinstance(data.get("summary"), str) or not data.get("summary", "").strip():
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.summary_missing",
                message="Enrichment summary must be a non-empty string.",
                severity="high",
                path="$.data.summary",
            )
        )
    if not _non_empty_string_list(data.get("evidence")):
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.evidence_missing",
                message="Enrichment must cite evidence instead of unsupported assertions.",
                severity="high",
                path="$.data.evidence",
            )
        )
    if not _non_empty_string_list(data.get("recommendations")):
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.recommendations_missing",
                message="Enrichment should provide at least one actionable recommendation.",
                severity="medium",
                path="$.data.recommendations",
            )
        )
    confidence = data.get("confidence")
    if not isinstance(confidence, int | float) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.confidence_invalid",
                message="Enrichment confidence must be a number between 0 and 1.",
                severity="critical",
                path="$.data.confidence",
            )
        )
    elif confidence < 0.55 and data.get("review_required") is not True:
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.low_confidence_not_reviewable",
                message="Low-confidence enrichment must remain review_required.",
                severity="high",
                path="$.data.review_required",
            )
        )
    if not isinstance(data.get("review_required"), bool):
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.review_required_invalid",
                message="review_required must be a boolean.",
                severity="critical",
                path="$.data.review_required",
            )
        )
    return findings


def _boundary_findings(deterministic_result: dict[str, Any], data: dict[str, Any]) -> list[EnrichmentQualityFinding]:
    findings: list[EnrichmentQualityFinding] = []
    decisions = _deterministic_decisions(deterministic_result)
    deterministic_status = str(deterministic_result.get("status") or "").upper()
    needs_decisions = bool(decisions) or deterministic_status == "NEEDS_DECISIONS"
    readiness_claim = _has_readiness_claim(data)
    if needs_decisions and data.get("review_required") is False:
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.review_boundary_removed",
                message="Enrichment must not remove review_required when deterministic output needs decisions.",
                severity="critical",
                path="$.data.review_required",
            )
        )
    if needs_decisions and readiness_claim:
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.review_readiness_claim",
                message="Enrichment must not claim the output is ready to deploy when deterministic output needs decisions.",
                severity="high",
                path="$.data",
            )
        )
    if deterministic_status in {"FAIL", "INVALID", "UNSAFE", "UNSUPPORTED"} and readiness_claim:
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.blocking_readiness_claim",
                message="Enrichment must not recommend proceeding when deterministic output is blocking.",
                severity="critical",
                path="$.data",
            )
        )
    if decisions and not _non_empty_string_list(data.get("decisions_required")):
        findings.append(
            EnrichmentQualityFinding(
                code="enrichment.decisions_hidden",
                message="Enrichment must preserve or restate deterministic required decisions.",
                severity="critical",
                path="$.data.decisions_required",
            )
        )
    return findings


def _has_readiness_claim(data: dict[str, Any]) -> bool:
    text = " ".join(
        str(item)
        for item in [
            data.get("summary"),
            *(_string_items(data.get("recommendations"))),
        ]
        if item
    ).lower()
    if not text:
        return False
    return re.search(r"\b(ready|proceed|deploy|run|execute|publish|production-ready)\b", text) is not None


def _secret_findings(data: dict[str, Any]) -> list[EnrichmentQualityFinding]:
    redacted = redact_secrets(data)
    if redacted == data:
        return []
    return [
        EnrichmentQualityFinding(
            code="enrichment.secret_leak",
            message="Enrichment data contains a secret-like field or inline secret assignment.",
            severity="critical",
        )
    ]


def _deterministic_decisions(payload: Any) -> list[str]:
    decisions: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "decisions_required":
                if isinstance(value, list):
                    decisions.extend(_decision_text(item) for item in value if _decision_text(item))
            elif key == "missing_fields" and isinstance(value, list):
                decisions.extend(str(item) for item in value if item)
            else:
                decisions.extend(_deterministic_decisions(value))
    elif isinstance(payload, list):
        for item in payload:
            decisions.extend(_deterministic_decisions(item))
    return decisions


def _decision_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("question") or value.get("path") or "")
    return ""


def _non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and any(isinstance(item, str) and item.strip() for item in value)


def _string_items(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _report(findings: list[EnrichmentQualityFinding]) -> EnrichmentQualityReport:
    score = _score(findings)
    status: EnrichmentQualityStatus
    if any(finding.severity in {"critical", "high"} for finding in findings):
        status = "FAIL"
    elif findings:
        status = "WARN"
    else:
        status = "PASS"
    summary = _summary(status, score, findings)
    return EnrichmentQualityReport(status=status, score=score, summary=summary, findings=findings)


def _score(findings: list[EnrichmentQualityFinding]) -> float:
    penalty = 0.0
    for finding in findings:
        penalty += {"critical": 0.35, "high": 0.22, "medium": 0.10}[finding.severity]
    return max(0.0, round(1.0 - penalty, 2))


def _summary(status: EnrichmentQualityStatus, score: float, findings: list[EnrichmentQualityFinding]) -> str:
    if status == "PASS":
        return "Enrichment preserves deterministic boundaries and provides usable evidence."
    if status == "WARN":
        return f"Enrichment is usable with review. Score {score:.2f}; {len(findings)} warning(s)."
    return f"Enrichment should not be trusted. Score {score:.2f}; {len(findings)} blocking finding(s)."


def load_json_payload(path: str) -> dict[str, Any]:
    """Load a JSON object for CLI evaluation."""

    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path!r}.")
    return payload
