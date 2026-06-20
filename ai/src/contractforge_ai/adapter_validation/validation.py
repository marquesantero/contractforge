"""Deterministic validation against optional platform adapter planners."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from contractforge_ai.adapter_validation.models import AdapterPlanningOutcome, AdapterValidationStatus
from contractforge_ai.adapter_validation.registry import adapter_planner_spec, known_adapter_names
from contractforge_ai.models import EvidenceItem, Finding, Severity

_SUPPORTED = "SUPPORTED"
_SUPPORTED_WITH_WARNINGS = "SUPPORTED_WITH_WARNINGS"
_REVIEW_REQUIRED = "REVIEW_REQUIRED"
_UNSUPPORTED = "UNSUPPORTED"

_ARTIFACT_TYPE_SUFFIXES: tuple[tuple[str, str], ...] = (
    (".databricks.yml", "databricks_asset_bundle"),
    (".fabric.notebook.py", "fabric_notebook"),
    (".fabric.deployment.json", "fabric_deployment"),
    (".gcp.source_materialization.json", "gcp_source_materialization"),
    (".gcp.write.sql", "gcp_write_sql"),
    (".gcp.advanced_write_mode_review.json", "gcp_advanced_write_review"),
    (".snowflake.runtime.sql", "snowflake_runtime_sql"),
    (".snowflake.task_graph.sql", "snowflake_task_graph_sql"),
    (".contract.json", "contract_snapshot"),
    (".glue_job.py", "aws_glue_job_runtime"),
    (".glue_job_definition.json", "aws_glue_job_definition"),
    (".deployment_manifest.json", "deployment_manifest"),
    (".cloudformation.json", "cloudformation"),
    (".tf", "terraform"),
    (".iam_policy.json", "iam_policy"),
    (".lakeformation.json", "lake_formation"),
    (".evidence_ddl.sql", "evidence_ddl_sql"),
    (".state_ddl.sql", "state_ddl_sql"),
    (".evidence.sql", "evidence_sql"),
    (".quality.dqdl", "quality_dqdl"),
    (".quality.sql", "quality_sql"),
    (".governance.sql", "governance_sql"),
    (".annotations.sql", "annotations_sql"),
    (".operations.json", "operations_json"),
    (".strategy.json", "strategy_json"),
    (".md", "review_markdown"),
    (".sql", "sql"),
    (".json", "json"),
    (".py", "python"),
    (".yml", "yaml"),
    (".yaml", "yaml"),
)


def validate_contract_with_adapter(
    contract: dict[str, Any],
    *,
    adapter: str,
    environment: dict[str, Any] | None = None,
) -> AdapterPlanningOutcome:
    """Plan one contract through an optional adapter public API."""

    normalized_adapter = adapter.strip().lower()
    spec = adapter_planner_spec(normalized_adapter)
    if spec is None:
        return _unknown_adapter(normalized_adapter)
    try:
        module = import_module(spec.module)
        planner = getattr(module, spec.function)
    except ModuleNotFoundError as exc:
        missing = exc.name or spec.module
        return _package_unavailable(normalized_adapter, missing)
    except Exception as exc:
        return _adapter_import_failed(normalized_adapter, exc)
    try:
        kwargs = dict(spec.kwargs)
        if environment is not None:
            kwargs["environment"] = environment
        result = planner(contract, **kwargs)
    except Exception as exc:
        return _planning_failed(normalized_adapter, exc)

    raw_status = _status_text(getattr(result, "status", "UNKNOWN"))
    artifact_names, artifact_types, render_findings = _render_artifact_summary(
        normalized_adapter,
        spec,
        module,
        contract,
        environment=environment,
    )
    findings = [
        *_findings_from_planning(normalized_adapter, result, raw_status),
        *render_findings,
    ]
    status = _validation_status(raw_status, findings)
    evidence = [
        EvidenceItem(
            source=f"contractforge_{normalized_adapter}",
            reason="Planned generated contract through the adapter public planning API.",
            value={
                "planning_status": raw_status,
                "blocker_codes": _issue_codes(getattr(result, "blockers", ()) or ()),
                "warning_codes": _issue_codes(getattr(result, "warnings", ()) or ()),
                "artifact_count": len(artifact_names),
                "artifact_types": artifact_types,
                "artifact_names": artifact_names,
            },
            confidence=1.0,
        )
    ]
    return AdapterPlanningOutcome(
        adapter=normalized_adapter,
        status=status,
        summary=f"{normalized_adapter} adapter planning returned {raw_status}.",
        findings=findings,
        evidence=evidence,
        raw_status=raw_status,
        artifact_names=artifact_names,
        artifact_types=artifact_types,
    )


def _validation_status(raw_status: str, findings: list[Finding]) -> AdapterValidationStatus:
    if raw_status == _UNSUPPORTED or any(item.severity in {"high", "critical"} for item in findings):
        return "INVALID"
    if raw_status in {_SUPPORTED_WITH_WARNINGS, _REVIEW_REQUIRED} or findings:
        return "NEEDS_DECISIONS"
    if raw_status == _SUPPORTED:
        return "READY"
    return "NEEDS_DECISIONS"


def _findings_from_planning(adapter: str, result: Any, raw_status: str) -> list[Finding]:
    findings: list[Finding] = []
    for blocker in tuple(getattr(result, "blockers", ()) or ()):
        findings.append(
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.planning.blocker.{_safe_code(getattr(blocker, 'code', 'unknown'))}",
                severity="high",
                title=f"{adapter} adapter cannot plan this contract",
                detail=str(getattr(blocker, "message", blocker)),
                recommendation="Change the contract semantics or select an adapter/runtime that declares the required capability.",
            )
        )
    for warning in tuple(getattr(result, "warnings", ()) or ()):
        findings.append(
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.planning.warning.{_safe_code(getattr(warning, 'code', 'unknown'))}",
                severity="medium",
                title=f"{adapter} adapter planning warning",
                detail=str(getattr(warning, "message", warning)),
                recommendation="Review the adapter warning before deployment; do not let AI silently accept changed semantics.",
            )
        )
    if raw_status == _REVIEW_REQUIRED and not findings:
        findings.append(
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.planning.review_required",
                severity="medium",
                title=f"{adapter} adapter requires review",
                detail="The adapter planner returned REVIEW_REQUIRED.",
                recommendation="Review the generated contract and adapter plan before deployment.",
            )
        )
    if raw_status == _UNSUPPORTED and not findings:
        findings.append(
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.planning.unsupported",
                severity="high",
                title=f"{adapter} adapter does not support this contract",
                detail="The adapter planner returned UNSUPPORTED.",
                recommendation="Change unsupported semantics or target another adapter/runtime.",
            )
        )
    return findings


def _render_artifact_summary(
    adapter: str,
    spec: Any,
    module: Any,
    contract: dict[str, Any],
    *,
    environment: dict[str, Any] | None,
) -> tuple[list[str], list[str], list[Finding]]:
    if not spec.render_function:
        return [], [], []
    if _contains_review_required(contract):
        return [], [], [
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.render_review_required",
                severity="medium",
                title=f"{adapter} adapter rendering requires review",
                detail="The contract still contains REVIEW_REQUIRED placeholders, so AI validation stopped before rendering native artifacts.",
                recommendation="Resolve review placeholders deterministically before treating adapter rendering as deployable.",
            )
        ]
    try:
        renderer = getattr(module, spec.render_function)
    except AttributeError:
        return [], [], [
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.render_api_missing",
                severity="medium",
                title=f"{adapter} adapter render API is missing",
                detail=f"{spec.module}.{spec.render_function} is not available.",
                recommendation="Expose the adapter public render API so AI validation can report native artifact types.",
            )
        ]
    try:
        kwargs = dict(spec.kwargs)
        if environment is not None:
            kwargs["environment"] = environment
        rendered = renderer(contract, **kwargs)
    except Exception as exc:
        return [], [], [
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.render_failed",
                severity="high",
                title=f"{adapter} adapter render failed",
                detail=f"{type(exc).__name__}: {exc}",
                recommendation="Fix the contract or adapter renderer before treating generated artifacts as deployable.",
            )
        ]
    artifact_names = sorted(str(name) for name in _artifact_mapping(rendered))
    artifact_types = sorted({_artifact_type(name) for name in artifact_names})
    return artifact_names, artifact_types, []


def _artifact_mapping(rendered: Any) -> dict[str, Any]:
    artifacts = getattr(rendered, "artifacts", None)
    return artifacts if isinstance(artifacts, dict) else {}


def _artifact_type(name: str) -> str:
    normalized = name.lower()
    for suffix, artifact_type in _ARTIFACT_TYPE_SUFFIXES:
        if normalized.endswith(suffix):
            return artifact_type
    return "artifact"


def _contains_review_required(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_review_required(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_review_required(item) for item in value)
    return value == "REVIEW_REQUIRED"


def _status_text(value: Any) -> str:
    text = getattr(value, "value", value)
    return str(text).split(".")[-1].upper()


def _issue_codes(issues: Any) -> list[str]:
    return [
        _safe_code(getattr(issue, "code", "unknown"))
        for issue in tuple(issues or ())
    ]


def _unknown_adapter(adapter: str) -> AdapterPlanningOutcome:
    return AdapterPlanningOutcome(
        adapter=adapter,
        status="NEEDS_DECISIONS",
        summary=f"Adapter {adapter!r} is not registered for deterministic AI planning validation.",
        findings=[
            _finding(
                adapter=adapter,
                code="adapter.validation.unknown_adapter",
                severity="medium",
                title="Unknown adapter requested",
                detail=f"Known adapters: {', '.join(known_adapter_names())}.",
                recommendation="Register a public adapter planner or use one of the known adapter names.",
            )
        ],
        evidence=[_evidence(adapter, "Adapter name was not found in the deterministic validation registry.")],
    )


def _package_unavailable(adapter: str, missing: str) -> AdapterPlanningOutcome:
    return AdapterPlanningOutcome(
        adapter=adapter,
        status="NEEDS_DECISIONS",
        summary=f"{adapter} adapter package is not available, so adapter planning was skipped.",
        findings=[
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.package_unavailable",
                severity="medium",
                title=f"{adapter} adapter package is not installed",
                detail=f"Import failed because {missing!r} is not available.",
                recommendation=f"Install the {adapter} adapter extra/package before treating adapter planning as complete.",
            )
        ],
        evidence=[_evidence(adapter, "Adapter package was unavailable during deterministic validation.")],
    )


def _adapter_import_failed(adapter: str, exc: Exception) -> AdapterPlanningOutcome:
    return AdapterPlanningOutcome(
        adapter=adapter,
        status="NEEDS_DECISIONS",
        summary=f"{adapter} adapter import failed.",
        findings=[
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.import_failed",
                severity="medium",
                title=f"{adapter} adapter import failed",
                detail=f"{type(exc).__name__}: {exc}",
                recommendation="Repair the adapter installation before relying on adapter-aware AI validation.",
            )
        ],
        evidence=[_evidence(adapter, "Adapter import failed during deterministic validation.")],
    )


def _planning_failed(adapter: str, exc: Exception) -> AdapterPlanningOutcome:
    return AdapterPlanningOutcome(
        adapter=adapter,
        status="INVALID",
        summary=f"{adapter} adapter rejected the generated contract during planning.",
        findings=[
            _finding(
                adapter=adapter,
                code=f"adapter.{adapter}.planning_failed",
                severity="high",
                title=f"{adapter} adapter planning failed",
                detail=f"{type(exc).__name__}: {exc}",
                recommendation="Fix the contract so the adapter public planner can evaluate it deterministically.",
            )
        ],
        evidence=[_evidence(adapter, "Adapter planner raised an exception during deterministic validation.")],
    )


def _finding(
    *,
    adapter: str,
    code: str,
    severity: Severity,
    title: str,
    detail: str,
    recommendation: str,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        title=title,
        detail=detail,
        recommendation=recommendation,
        evidence=[_evidence(adapter, f"Adapter validation rule {code!r} identified this condition.")],
    )


def _evidence(adapter: str, reason: str) -> EvidenceItem:
    return EvidenceItem(source=f"contractforge_{adapter}", reason=reason, confidence=1.0)


def _safe_code(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in str(value)).strip("_") or "unknown"
