"""Deterministic validation for generated artifacts."""

from __future__ import annotations

from typing import Any

import yaml

from contractforge_ai.models import EvidenceItem, Finding, Severity, Traceability, ValidationResult
from contractforge_ai.write_modes import canonical_write_mode

MERGE_MODES = {"scd1_upsert", "scd1_hash_diff", "scd2_historical", "snapshot_soft_delete"}
REVIEW_PLACEHOLDER = "REVIEW_REQUIRED"


def validate_generated_contract(contract: dict[str, Any]) -> ValidationResult:
    """Validate a generated ContractForge contract draft without requiring Spark or ContractForge core."""

    findings: list[Finding] = []

    if not isinstance(contract, dict):
        return ValidationResult(
            status="FAIL",
            summary="Generated artifact is not a contract mapping.",
            findings=[
                _finding(
                    code="generated.contract.invalid_type",
                    severity="critical",
                    title="Generated contract is not a mapping",
                    detail="The generated contract must be a dictionary-like mapping.",
                    recommendation="Regenerate the contract or inspect the generator output.",
                )
            ],
            traceability=_traceability(findings_count=1, confidence=1.0, review_required=True),
        )

    _check_yaml_serializable(contract, findings)
    _check_draft_metadata(contract, findings)
    _check_source(contract, findings)
    _check_target(contract, findings)
    _check_write_mode(contract, findings)
    _check_review_placeholders(contract, findings)

    status = _status(findings)
    return ValidationResult(
        status=status,
        summary=_summary(status, findings),
        findings=findings,
        traceability=_traceability(
            findings_count=len(findings),
            confidence=1.0,
            review_required=status != "PASS",
        ),
    )


def _check_yaml_serializable(contract: dict[str, Any], findings: list[Finding]) -> None:
    try:
        yaml.safe_dump(contract, sort_keys=False)
    except Exception as exc:
        findings.append(
            _finding(
                code="generated.contract.yaml_unserializable",
                severity="critical",
                title="Generated contract is not YAML serializable",
                detail=f"YAML serialization failed: {type(exc).__name__}: {exc}",
                recommendation="Inspect generated values and remove non-serializable objects.",
            )
        )


def _check_draft_metadata(contract: dict[str, Any], findings: list[Finding]) -> None:
    metadata = _mapping(contract.get("_metadata"))
    if metadata.get("draft") is not True:
        findings.append(
            _finding(
                code="generated.metadata.draft_missing",
                severity="medium",
                title="Draft marker is missing",
                detail="Generated contracts should include _metadata.draft: true.",
                recommendation="Mark generated contracts as drafts until reviewed.",
                path="_metadata.draft",
            )
        )
    if metadata.get("review_required") is not True:
        findings.append(
            _finding(
                code="generated.metadata.review_required_missing",
                severity="medium",
                title="Review marker is missing",
                detail="Generated contracts should include _metadata.review_required: true.",
                recommendation="Mark generated contracts as requiring review.",
                path="_metadata.review_required",
            )
        )


def _check_source(contract: dict[str, Any], findings: list[Finding]) -> None:
    source = _mapping(contract.get("source"))
    if not source:
        findings.append(
            _finding(
                code="generated.source.missing",
                severity="critical",
                title="Source block is missing",
                detail="Generated contracts must include a source block.",
                recommendation="Provide source connector/type and source location details.",
                path="source",
            )
        )
        return

    connector = source.get("connector") or source.get("type")
    if not connector:
        findings.append(
            _finding(
                code="generated.source.connector_missing",
                severity="high",
                title="Source connector is missing",
                detail="Generated contracts should declare the source connector or type.",
                recommendation="Set source.connector for connector-based contracts.",
                path="source.connector",
            )
        )

    if not any(source.get(key) for key in ("path", "table", "query", "url")):
        findings.append(
            _finding(
                code="generated.source.location_missing",
                severity="high",
                title="Source location is missing",
                detail="Generated contracts should include a source path, table, query or URL.",
                recommendation="Provide the source location explicitly.",
                path="source",
            )
        )


def _check_target(contract: dict[str, Any], findings: list[Finding]) -> None:
    target = _mapping(contract.get("target"))
    for key in ("catalog", "schema", "table"):
        if not target.get(key):
            findings.append(
                _finding(
                    code=f"generated.target.{key}_missing",
                    severity="high" if key != "table" else "critical",
                    title=f"Target {key} is missing",
                    detail=f"Generated contracts should declare target.{key}.",
                    recommendation=f"Set target.{key} before using this contract.",
                    path=f"target.{key}",
                )
            )


def _check_write_mode(contract: dict[str, Any], findings: list[Finding]) -> None:
    declared_mode = str(contract.get("mode") or "").strip()
    if not declared_mode:
        findings.append(
            _finding(
                code="generated.mode.missing",
                severity="critical",
                title="Write mode is missing",
                detail="Generated contracts must include a write mode.",
                recommendation="Set mode to a supported ContractForge write mode.",
                path="mode",
            )
        )
        return

    mode = canonical_write_mode(declared_mode)
    if mode not in MERGE_MODES:
        return

    merge_keys = _list(contract.get("merge_keys") or contract.get("keys"))
    if not merge_keys:
        findings.append(
            _finding(
                code="generated.merge_keys.missing",
                severity="critical",
                title="Merge keys are missing",
                detail=f"Mode {declared_mode!r} requires merge keys.",
                recommendation="Set merge_keys after confirming the business key.",
                path="merge_keys",
            )
        )
        return

    not_null = set(_list(_mapping(contract.get("quality_rules")).get("not_null")))
    missing_not_null = [key for key in merge_keys if key not in not_null]
    if missing_not_null:
        findings.append(
            _finding(
                code="generated.merge_keys.not_null_missing",
                severity="high",
                title="Merge keys are not protected by not_null",
                detail=f"Missing not_null checks for: {', '.join(missing_not_null)}.",
                recommendation="Add all merge keys to quality_rules.not_null.",
                path="quality_rules.not_null",
            )
        )


def _check_review_placeholders(contract: dict[str, Any], findings: list[Finding]) -> None:
    placeholder_paths = _placeholder_paths(contract)
    for path in placeholder_paths:
        findings.append(
            _finding(
                code="generated.review_placeholder",
                severity="medium",
                title="Review placeholder remains",
                detail=f"{path} still contains REVIEW_REQUIRED.",
                recommendation="Replace placeholders before using the contract in production.",
                path=path,
            )
        )


def _placeholder_paths(value: Any, *, prefix: str = "") -> list[str]:
    if value == REVIEW_PLACEHOLDER:
        return [prefix or "$"]
    if isinstance(value, dict):
        result: list[str] = []
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            result.extend(_placeholder_paths(item, prefix=child))
        return result
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value):
            child = f"{prefix}[{index}]" if prefix else f"[{index}]"
            result.extend(_placeholder_paths(item, prefix=child))
        return result
    return []


def _finding(
    *,
    code: str,
    severity: Severity,
    title: str,
    detail: str,
    recommendation: str,
    path: str | None = None,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        title=title,
        detail=detail,
        recommendation=recommendation,
        path=path,
        evidence=[
            EvidenceItem(
                source="generated_contract",
                path=path,
                reason=f"Deterministic generated-contract validation rule {code!r} identified this condition.",
                confidence=1.0,
            )
        ],
    )


def _traceability(*, findings_count: int, confidence: float, review_required: bool) -> Traceability:
    return Traceability(
        confidence=confidence,
        evidence=[
            EvidenceItem(
                source="generated_contract",
                reason="Validated generated contract structure with deterministic rules.",
                value={"findings": findings_count},
                confidence=confidence,
            )
        ],
        review_required=review_required,
    )


def _status(findings: list[Finding]) -> str:
    severities = {finding.severity for finding in findings}
    if {"critical", "high"} & severities:
        return "FAIL"
    if findings:
        return "WARN"
    return "PASS"


def _summary(status: str, findings: list[Finding]) -> str:
    if not findings:
        return "Generated contract passed deterministic validation."
    critical = sum(1 for finding in findings if finding.severity == "critical")
    high = sum(1 for finding in findings if finding.severity == "high")
    medium = sum(1 for finding in findings if finding.severity == "medium")
    return f"{status}: {len(findings)} finding(s), including {critical} critical, {high} high and {medium} medium."


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []
