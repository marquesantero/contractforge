"""Deterministic failure explanation for ContractForge run evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contractforge_ai.context.redaction import redact_secrets
from contractforge_ai.models import EvidenceItem, FailureExplanation, Finding, Severity, Traceability


PATTERNS: dict[str, dict[str, Any]] = {
    "authentication_or_authorization": {
        "severity": "high",
        "confidence": 0.88,
        "regex": re.compile(
            r"(unauthorized|permission[_ -]?denied|access denied|forbidden|invalid credential|"
            r"authentication failed|authorization|jwt|token invalid|mfa|403\b)",
            re.IGNORECASE,
        ),
        "title": "Authentication or authorization failure",
        "recommendation": "Validate credentials, grants, secret values, token scope and runtime identity permissions.",
    },
    "network_or_egress": {
        "severity": "high",
        "confidence": 0.86,
        "regex": re.compile(
            r"(temporary failure in name resolution|dns|name resolution|egress|network|socket|"
            r"connection refused|connect timed out|timeout|host unreachable)",
            re.IGNORECASE,
        ),
        "title": "Network, DNS or egress failure",
        "recommendation": "Validate workspace egress, DNS resolution, firewall rules, private endpoints and network policies.",
    },
    "storage_access": {
        "severity": "high",
        "confidence": 0.84,
        "regex": re.compile(
            r"(abfs|abfss|s3a|wasbs|external location|cloud storage|sas|"
            r"AuthorizationPermissionMismatch|storage credential|read files|list permission)",
            re.IGNORECASE,
        ),
        "title": "Cloud storage access failure",
        "recommendation": "Check External Location, storage credential, SAS/list permissions and object storage path scope.",
    },
    "schema_or_sql": {
        "severity": "medium",
        "confidence": 0.82,
        "regex": re.compile(
            r"(schema mismatch|cannot resolve|analysisexception|parse_syntax_error|syntax error|"
            r"invalid identifier|cannot cast|data type|incompatible schema|missing column)",
            re.IGNORECASE,
        ),
        "title": "Schema, SQL or type compatibility failure",
        "recommendation": "Validate source schema, target schema policy, generated SQL, column names and type widening rules.",
    },
    "quality_gate": {
        "severity": "medium",
        "confidence": 0.82,
        "regex": re.compile(
            r"(quality|quarantine|failed_count|not_null|accepted_values|max_null_ratio|min_rows|expectation)",
            re.IGNORECASE,
        ),
        "title": "Quality gate failure",
        "recommendation": "Inspect quality rule results, quarantined rows and whether the rule should warn, quarantine or abort.",
    },
    "dependency_or_driver": {
        "severity": "high",
        "confidence": 0.84,
        "regex": re.compile(
            r"(module not found|modulenotfounderror|classnotfound|no suitable driver|package not found|"
            r"library installation failed|missing dependency|importerror)",
            re.IGNORECASE,
        ),
        "title": "Missing dependency, library or driver",
        "recommendation": "Install the required connector library/driver on the selected runtime and verify version compatibility.",
    },
    "runtime_limitation": {
        "severity": "high",
        "confidence": 0.80,
        "regex": re.compile(
            r"(spark connect|serverless|unsupported|not supported|deltaTable|java gateway|"
            r"runtime limitation|not implemented)",
            re.IGNORECASE,
        ),
        "title": "Runtime capability limitation",
        "recommendation": "Check the runtime compatibility matrix and use a supported path for serverless/classic execution.",
    },
    "api_rate_or_quota": {
        "severity": "medium",
        "confidence": 0.78,
        "regex": re.compile(r"(429|rate limit|too many requests|quota|throttl)", re.IGNORECASE),
        "title": "API rate limit or quota failure",
        "recommendation": "Reduce request rate, add pagination/backoff controls or increase provider quota.",
    },
}


def explain_failure(path: str | Path | dict[str, Any]) -> FailureExplanation:
    """Explain a failed run from a JSON file or already-loaded evidence mapping."""

    evidence = _load_evidence(path)
    text = _evidence_text(evidence)
    findings = _classify(text)

    if not findings:
        return FailureExplanation(
            status="UNKNOWN",
            primary_category="unknown",
            risk="medium",
            confidence=0.0,
            summary="No known failure pattern matched the supplied evidence.",
            findings=[],
            recommended_actions=[
                "Inspect the full error stack trace.",
                "Check source connector metadata, runtime type and recent contract changes.",
                "Add a regression fixture if this is a recurring failure mode.",
            ],
            evidence=_summarize_evidence(evidence),
            traceability=Traceability(
                confidence=0.0,
                evidence=[
                    EvidenceItem(
                        source="run_evidence",
                        reason="No deterministic failure pattern matched the supplied evidence.",
                        confidence=0.0,
                    )
                ],
                review_required=True,
            ),
        )

    primary = findings[0]
    category = primary.code.removeprefix("failure.")
    confidence = _pattern_confidence(category)
    risk = _max_risk([finding.severity for finding in findings])

    return FailureExplanation(
        status="EXPLAINED",
        primary_category=category,
        risk=risk,
        confidence=confidence,
        summary=f"Most likely cause: {primary.title}.",
        findings=findings,
        recommended_actions=_recommended_actions(findings),
        evidence=_summarize_evidence(evidence),
        traceability=Traceability(
            confidence=confidence,
            evidence=[
                EvidenceItem(
                    source="run_evidence",
                    reason=f"Matched {len(findings)} deterministic failure pattern(s).",
                    value=[finding.code for finding in findings],
                    confidence=confidence,
                )
            ],
            review_required=confidence < 0.80,
        ),
    )


def _load_evidence(path_or_mapping: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(path_or_mapping, dict):
        return redact_secrets(path_or_mapping)

    path = Path(path_or_mapping)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Failure evidence must be a JSON object.")
    return redact_secrets(data)


def _evidence_text(evidence: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("error_message", "stack_trace", "traceback", "status", "runtime_type", "source_connector"):
        value = evidence.get(key)
        if value is not None:
            parts.append(str(value))

    run = evidence.get("run")
    if isinstance(run, dict):
        for key in (
            "error_message",
            "status",
            "runtime_type",
            "source_connector",
            "source_type",
            "target_table",
            "mode",
        ):
            value = run.get(key)
            if value is not None:
                parts.append(str(value))

    for collection_key in ("errors", "quality", "streams", "events"):
        collection = evidence.get(collection_key)
        if isinstance(collection, list):
            for item in collection:
                if isinstance(item, dict):
                    parts.extend(str(value) for value in item.values() if value is not None)
                elif item is not None:
                    parts.append(str(item))

    return "\n".join(parts)


def _classify(text: str) -> list[Finding]:
    matches: list[Finding] = []
    for category, spec in PATTERNS.items():
        if spec["regex"].search(text):
            matches.append(
                Finding(
                    code=f"failure.{category}",
                    severity=spec["severity"],
                    title=spec["title"],
                    detail=f"Evidence matched the {category.replace('_', ' ')} failure pattern.",
                    recommendation=spec["recommendation"],
                    evidence=[
                        EvidenceItem(
                            source="run_evidence",
                            reason=f"Regex pattern for {category.replace('_', ' ')} matched the supplied evidence.",
                            confidence=float(spec["confidence"]),
                        )
                    ],
                )
            )
    return sorted(matches, key=lambda finding: _severity_rank(finding.severity), reverse=True)


def _recommended_actions(findings: list[Finding]) -> list[str]:
    actions: list[str] = []
    for finding in findings:
        if finding.recommendation not in actions:
            actions.append(finding.recommendation)
    return actions


def _summarize_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    run = evidence.get("run") if isinstance(evidence.get("run"), dict) else evidence
    summary_keys = (
        "run_id",
        "parent_run_id",
        "status",
        "target_table",
        "mode",
        "source_connector",
        "runtime_type",
        "framework_version",
        "ctrl_schema_version",
    )
    return {key: run.get(key) for key in summary_keys if run.get(key) is not None}


def _pattern_confidence(category: str) -> float:
    spec = PATTERNS.get(category)
    return float(spec["confidence"]) if spec else 0.0


def _severity_rank(severity: Severity) -> int:
    return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[severity]


def _max_risk(severities: list[Severity]) -> Severity:
    return max(severities, key=_severity_rank) if severities else "info"

