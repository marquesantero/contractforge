"""Deterministic validation loop for AI-assisted artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

import yaml

from contractforge_ai.evaluation import StructuredOutputValidation, validate_model_output
from contractforge_ai.adapter_validation import validate_contract_with_adapter
from contractforge_ai.models import EvidenceItem, Finding, Severity, ValidationResult
from contractforge_ai.projects import ProjectArtifact, ProjectPlan
from contractforge_ai.validation.contractforge import validate_with_contractforge
from contractforge_ai.validation.generated import validate_generated_contract

ValidationGateStatus = Literal["READY", "NEEDS_DECISIONS", "INVALID", "UNSAFE"]
ValidationCheckKind = Literal["adapter", "contract", "contractforge", "model_output", "project", "artifact", "security"]

SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|sas)\s*[:=]\s*([^\s,;\]]+)",
    re.IGNORECASE,
)
SECRET_TEMPLATE_RE = re.compile(r"\{\{\s*secret:[^}]+\}\}", re.IGNORECASE)


@dataclass(frozen=True)
class DeterministicValidationCheck:
    """One validation check executed by the deterministic loop."""

    kind: ValidationCheckKind
    name: str
    status: ValidationGateStatus
    summary: str
    findings: list[Finding] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class DeterministicValidationReport:
    """Aggregated validation gate result for AI-assisted output."""

    status: ValidationGateStatus
    summary: str
    checks: list[DeterministicValidationCheck] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    decisions_required: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "READY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "summary": self.summary,
            "checks": [check.to_dict() for check in self.checks],
            "evidence": [item.to_dict() for item in self.evidence],
            "decisions_required": self.decisions_required,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Deterministic Validation Report",
            "",
            f"- Status: `{self.status}`",
            f"- Ready: `{str(self.ready).lower()}`",
            f"- Summary: {self.summary}",
            "",
            "## Checks",
        ]
        for check in self.checks:
            lines.extend(
                [
                    "",
                    f"### `{check.name}`",
                    "",
                    f"- Kind: `{check.kind}`",
                    f"- Status: `{check.status}`",
                    f"- Summary: {check.summary}",
                ]
            )
            if check.findings:
                lines.extend(["", "Findings:"])
                lines.extend(f"- `{finding.severity}` `{finding.code}`: {finding.title}" for finding in check.findings)
        if self.decisions_required:
            lines.extend(["", "## Decisions Required"])
            lines.extend(f"- {item}" for item in self.decisions_required)
        return "\n".join(lines).rstrip() + "\n"


def validate_contract_artifact(
    contract: dict[str, Any],
    *,
    use_contractforge: bool = True,
    adapters: tuple[str, ...] = (),
    adapter_environment: dict[str, Any] | None = None,
) -> DeterministicValidationReport:
    """Validate a generated ContractForge contract through deterministic checks."""

    checks = [_check_from_validation("contract", "generated_contract", validate_generated_contract(contract))]
    if use_contractforge:
        checks.append(_check_from_validation("contractforge", "contractforge_adapter", validate_with_contractforge(contract)))
    checks.extend(
        _check_from_adapter_validation(
            validate_contract_with_adapter(contract, adapter=adapter, environment=adapter_environment)
        )
        for adapter in adapters
    )
    return _aggregate(checks)


def validate_model_artifact(
    raw_output: str | dict[str, Any],
    *,
    prompt_name: str,
    deterministic_fallback: dict[str, Any] | None = None,
) -> DeterministicValidationReport:
    """Validate provider output against the registered prompt schema."""

    validation = validate_model_output(raw_output, prompt=prompt_name, deterministic_fallback=deterministic_fallback)
    check = _check_from_structured_output(prompt_name, validation)
    return _aggregate([check])


def validate_project_plan_artifact(
    plan: ProjectPlan,
    *,
    use_contractforge: bool = True,
    adapters: tuple[str, ...] = (),
) -> DeterministicValidationReport:
    """Validate a generated project plan and every supported artifact inside it."""

    checks: list[DeterministicValidationCheck] = [
        _project_decision_check(plan),
        *[
            _validate_project_artifact(
                artifact,
                all_artifacts=plan.artifacts,
                use_contractforge=use_contractforge,
                adapters=adapters,
            )
            for artifact in plan.artifacts
        ],
    ]
    return _aggregate(checks)


def _validate_project_artifact(
    artifact: ProjectArtifact,
    *,
    all_artifacts: list[ProjectArtifact],
    use_contractforge: bool,
    adapters: tuple[str, ...],
) -> DeterministicValidationCheck:
    unsafe = _unsafe_secret_findings(artifact.content, path=artifact.path)
    if unsafe:
        return DeterministicValidationCheck(
            kind="security",
            name=artifact.path,
            status="UNSAFE",
            summary="Artifact content contains inline secret-like values.",
            findings=unsafe,
            evidence=[_evidence("security", "Inline secret-like values were detected in generated artifact content.")],
        )

    if artifact.kind == "contract" or artifact.path.endswith((".ingestion.yaml", ".ingestion.yml", ".ingestion.json")):
        parsed = _parse_mapping_artifact(artifact)
        if isinstance(parsed, Finding):
            return DeterministicValidationCheck(
                kind="artifact",
                name=artifact.path,
                status="INVALID",
                summary="Contract artifact could not be parsed.",
                findings=[parsed],
            )
        parsed = _resolve_connection_source_for_artifact(parsed, all_artifacts)
        artifact_adapters = _adapters_for_artifact(artifact, requested=adapters)
        report = validate_contract_artifact(parsed, use_contractforge=use_contractforge, adapters=artifact_adapters)
        return DeterministicValidationCheck(
            kind="contract",
            name=artifact.path,
            status=report.status,
            summary=report.summary,
            findings=[finding for check in report.checks for finding in check.findings],
            evidence=report.evidence,
        )

    parse_finding = _syntax_finding_for_artifact(artifact)
    if parse_finding is not None:
        return DeterministicValidationCheck(
            kind="artifact",
            name=artifact.path,
            status="INVALID",
            summary="Artifact syntax validation failed.",
            findings=[parse_finding],
        )

    return DeterministicValidationCheck(
        kind="artifact",
        name=artifact.path,
        status="READY",
        summary="Artifact passed deterministic syntax/security checks.",
        evidence=[_evidence("artifact", "Artifact passed deterministic syntax/security checks.", path=artifact.path)],
    )


def _resolve_connection_source_for_artifact(
    contract: dict[str, Any],
    artifacts: list[ProjectArtifact],
) -> dict[str, Any]:
    source = contract.get("source")
    if not isinstance(source, dict) or source.get("type") != "connection":
        return contract
    connection_ref = str(source.get("connection_path") or "")
    if not connection_ref:
        return contract
    connection_path = _connection_artifact_path(connection_ref)
    connection = _connection_artifact_payload(artifacts, connection_path)
    if connection is None:
        return contract
    connection_source = _mapping(connection.get("source")) or connection
    overrides = {key: value for key, value in source.items() if key not in {"type", "connection_path"}}
    updated = dict(contract)
    updated["source"] = _deep_merge(dict(connection_source), overrides)
    return updated


def _connection_artifact_path(connection_ref: str) -> str:
    if connection_ref.startswith("project://"):
        return connection_ref.removeprefix("project://").strip("/\\")
    return connection_ref.strip()


def _connection_artifact_payload(artifacts: list[ProjectArtifact], path: str) -> dict[str, Any] | None:
    normalized = path.replace("\\", "/")
    for artifact in artifacts:
        if artifact.path.replace("\\", "/") != normalized:
            continue
        parsed = _parse_mapping_artifact(artifact)
        return parsed if isinstance(parsed, dict) else None
    return None


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _project_decision_check(plan: ProjectPlan) -> DeterministicValidationCheck:
    findings: list[Finding] = []
    for decision in plan.report.decisions_required:
        findings.append(
            _finding(
                code="project.decisions.required",
                severity="medium",
                title="Project still has required decisions",
                detail=decision.question,
                recommendation="Resolve required decisions before treating generated artifacts as ready.",
                path=decision.path,
                source="project_plan",
            )
        )
    for warning in plan.report.warnings:
        findings.append(
            _finding(
                code="project.warning.present",
                severity="medium",
                title="Project warning remains",
                detail=warning,
                recommendation="Review warning before treating generated artifacts as ready.",
                source="project_plan",
            )
        )
    status: ValidationGateStatus = "NEEDS_DECISIONS" if findings else "READY"
    return DeterministicValidationCheck(
        kind="project",
        name=plan.name,
        status=status,
        summary="Project decisions require review." if findings else "Project report has no open decisions.",
        findings=findings,
        evidence=[_evidence("project_plan", "Validated project report decisions and warnings.")],
    )


def _check_from_validation(
    kind: ValidationCheckKind,
    name: str,
    validation: ValidationResult,
) -> DeterministicValidationCheck:
    status = _status_from_validation(validation)
    return DeterministicValidationCheck(
        kind=kind,
        name=name,
        status=status,
        summary=validation.summary,
        findings=validation.findings,
        evidence=validation.traceability.evidence,
    )


def _check_from_structured_output(
    prompt_name: str,
    validation: StructuredOutputValidation,
) -> DeterministicValidationCheck:
    findings = [
        _finding(
            code=finding.code,
            severity=finding.severity,
            title="Structured output validation failed",
            detail=finding.message,
            recommendation="Repair or regenerate provider output before using it.",
            path=finding.path,
            source="model_output",
        )
        for finding in validation.findings
    ]
    return DeterministicValidationCheck(
        kind="model_output",
        name=prompt_name,
        status="READY" if validation.status == "PASS" else "INVALID",
        summary="Model output passed schema validation."
        if validation.status == "PASS"
        else "Model output failed schema validation.",
        findings=findings,
        evidence=[_evidence("model_output", f"Validated provider output against prompt schema {prompt_name!r}.")],
    )


def _check_from_adapter_validation(outcome) -> DeterministicValidationCheck:
    return DeterministicValidationCheck(
        kind="adapter",
        name=outcome.adapter,
        status=outcome.status,
        summary=outcome.summary,
        findings=outcome.findings,
        evidence=outcome.evidence,
    )


def _adapters_for_artifact(artifact: ProjectArtifact, *, requested: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(adapter.strip().lower() for adapter in requested if adapter and adapter.strip())
    if not normalized:
        return ()
    path_parts = artifact.path.replace("\\", "/").split("/")
    if "contracts" not in path_parts:
        return normalized
    index = path_parts.index("contracts")
    if len(path_parts) <= index + 1:
        return normalized
    inferred = path_parts[index + 1].strip().lower()
    return (inferred,) if inferred in normalized else ()


def _aggregate(checks: list[DeterministicValidationCheck]) -> DeterministicValidationReport:
    status = _aggregate_status(check.status for check in checks)
    findings = [finding for check in checks for finding in check.findings]
    evidence = [item for check in checks for item in check.evidence]
    decisions = [
        f"{finding.path}: {finding.title}" if finding.path else finding.title
        for finding in findings
        if finding.severity in {"medium", "high", "critical"} and status in {"NEEDS_DECISIONS", "INVALID", "UNSAFE"}
    ]
    return DeterministicValidationReport(
        status=status,
        summary=_summary(status, checks),
        checks=checks,
        evidence=evidence,
        decisions_required=decisions,
    )


def _aggregate_status(statuses: Any) -> ValidationGateStatus:
    ordered = list(statuses)
    if "UNSAFE" in ordered:
        return "UNSAFE"
    if "INVALID" in ordered:
        return "INVALID"
    if "NEEDS_DECISIONS" in ordered:
        return "NEEDS_DECISIONS"
    return "READY"


def _status_from_validation(validation: ValidationResult) -> ValidationGateStatus:
    if validation.status == "FAIL":
        return "INVALID"
    if validation.status == "WARN":
        return "NEEDS_DECISIONS"
    return "READY"


def _summary(status: ValidationGateStatus, checks: list[DeterministicValidationCheck]) -> str:
    counts = {item: sum(1 for check in checks if check.status == item) for item in ("READY", "NEEDS_DECISIONS", "INVALID", "UNSAFE")}
    return (
        f"{status}: {len(checks)} deterministic check(s), "
        f"{counts['READY']} ready, {counts['NEEDS_DECISIONS']} need decisions, "
        f"{counts['INVALID']} invalid, {counts['UNSAFE']} unsafe."
    )


def _parse_mapping_artifact(artifact: ProjectArtifact) -> dict[str, Any] | Finding:
    try:
        if artifact.path.endswith(".json"):
            parsed = json.loads(artifact.content)
        else:
            parsed = yaml.safe_load(artifact.content)
    except Exception as exc:
        return _finding(
            code="artifact.parse_failed",
            severity="critical",
            title="Artifact parse failed",
            detail=f"{type(exc).__name__}: {exc}",
            recommendation="Fix generated artifact syntax before validation.",
            path=artifact.path,
            source="artifact",
        )
    if not isinstance(parsed, dict):
        return _finding(
            code="artifact.not_mapping",
            severity="critical",
            title="Artifact is not a mapping",
            detail="Contract artifacts must parse to a mapping object.",
            recommendation="Regenerate the artifact as a YAML/JSON mapping.",
            path=artifact.path,
            source="artifact",
        )
    return parsed


def _syntax_finding_for_artifact(artifact: ProjectArtifact) -> Finding | None:
    try:
        if artifact.kind == "json" or artifact.path.endswith(".json"):
            json.loads(artifact.content)
        elif artifact.path.endswith(".toml"):
            tomllib.loads(artifact.content)
        elif artifact.kind in {"yaml", "config", "resource"} or artifact.path.endswith((".yaml", ".yml")):
            yaml.safe_load(artifact.content)
    except Exception as exc:
        return _finding(
            code="artifact.syntax_invalid",
            severity="critical",
            title="Artifact syntax is invalid",
            detail=f"{type(exc).__name__}: {exc}",
            recommendation="Fix generated syntax before writing or deploying this project.",
            path=artifact.path,
            source="artifact",
        )
    return None


def _unsafe_secret_findings(content: str, *, path: str) -> list[Finding]:
    findings: list[Finding] = []
    for match in SECRET_ASSIGNMENT_RE.finditer(content):
        line_start = content.rfind("\n", 0, match.start()) + 1
        line_end = content.find("\n", match.end())
        line = content[line_start:] if line_end == -1 else content[line_start:line_end]
        value = match.group(2)
        if value.startswith("[REDACTED") or SECRET_TEMPLATE_RE.search(line):
            continue
        findings.append(
            _finding(
                code="artifact.secret.inline_value",
                severity="critical",
                title="Inline secret-like value detected",
                detail=f"Generated artifact contains an inline value for {match.group(1)!r}.",
                recommendation="Use a secret reference or placeholder instead of writing credentials into generated artifacts.",
                path=path,
                source="security",
            )
        )
    return findings


def _finding(
    *,
    code: str,
    severity: Severity,
    title: str,
    detail: str,
    recommendation: str,
    source: str,
    path: str | None = None,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        title=title,
        detail=detail,
        recommendation=recommendation,
        path=path,
        evidence=[_evidence(source, f"Deterministic validation rule {code!r} identified this condition.", path=path)],
    )


def _evidence(source: str, reason: str, *, path: str | None = None) -> EvidenceItem:
    return EvidenceItem(source=source, reason=reason, path=path, confidence=1.0)
