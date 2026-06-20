"""Deterministic analysis for ContractForge control-table evidence."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

from contractforge_core.evidence import EVIDENCE_TABLES, STATE_TABLES
from contractforge_ai.context.redaction import redact_secrets
from contractforge_ai.models import EvidenceItem, Finding, Severity, Traceability


@dataclass(frozen=True)
class ControlTableScope:
    """Scope represented by a control-table evidence package."""

    catalog: str | None = None
    ctrl_schema: str | None = None
    target_table: str | None = None
    layer: str | None = None
    domain: str | None = None
    window: str | None = None
    platform: str | None = None
    evidence_store: str | None = None
    database: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in self.__dict__.items() if value is not None}


@dataclass(frozen=True)
class ControlTableEvidencePackage:
    """Redacted evidence collected from ContractForge control tables."""

    scope: ControlTableScope = field(default_factory=ControlTableScope)
    runs: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    quality: list[dict[str, Any]] = field(default_factory=list)
    quarantine: list[dict[str, Any]] = field(default_factory=list)
    streams: list[dict[str, Any]] = field(default_factory=list)
    schema_changes: list[dict[str, Any]] = field(default_factory=list)
    lineage: list[dict[str, Any]] = field(default_factory=list)
    metadata: list[dict[str, Any]] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)
    access: list[dict[str, Any]] = field(default_factory=list)
    operations: list[dict[str, Any]] = field(default_factory=list)
    cost: list[dict[str, Any]] = field(default_factory=list)
    state: list[dict[str, Any]] = field(default_factory=list)
    locks: list[dict[str, Any]] = field(default_factory=list)
    collection_errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope.to_dict(),
            "runs": self.runs,
            "errors": self.errors,
            "quality": self.quality,
            "quarantine": self.quarantine,
            "streams": self.streams,
            "schema_changes": self.schema_changes,
            "lineage": self.lineage,
            "metadata": self.metadata,
            "annotations": self.annotations,
            "access": self.access,
            "operations": self.operations,
            "cost": self.cost,
            "state": self.state,
            "locks": self.locks,
            "collection_errors": self.collection_errors,
        }


@dataclass(frozen=True)
class ControlTableAnalysis:
    """Structured operational analysis generated from control-table evidence."""

    status: str
    risk: Severity
    summary: str
    metrics: dict[str, Any]
    findings: list[Finding] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    follow_up_queries: list[str] = field(default_factory=list)
    traceability: Traceability = field(default_factory=Traceability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "risk": self.risk,
            "summary": self.summary,
            "metrics": self.metrics,
            "findings": [finding.to_dict() for finding in self.findings],
            "recommendations": self.recommendations,
            "follow_up_queries": self.follow_up_queries,
            "traceability": self.traceability.to_dict(),
        }

    def to_markdown(self) -> str:
        lines = [
            "# ContractForge Operational Analysis",
            "",
            f"- Status: `{self.status}`",
            f"- Risk: `{self.risk}`",
            f"- Summary: {self.summary}",
            "",
            "## Metrics",
        ]
        for key, value in self.metrics.items():
            lines.append(f"- `{key}`: `{value}`")
        if self.findings:
            lines.extend(["", "## Findings"])
            for finding in self.findings:
                lines.extend(
                    [
                        f"### {finding.title}",
                        f"- Severity: `{finding.severity}`",
                        f"- Code: `{finding.code}`",
                        f"- Detail: {finding.detail}",
                        f"- Recommendation: {finding.recommendation}",
                    ]
                )
        if self.recommendations:
            lines.extend(["", "## Recommendations", *[f"- {item}" for item in self.recommendations]])
        if self.follow_up_queries:
            lines.extend(["", "## Follow-up Queries", *[f"- `{item}`" for item in self.follow_up_queries]])
        lines.extend(["", self.traceability.to_markdown()])
        return "\n".join(lines).rstrip() + "\n"


def load_control_table_evidence(path: str | Path | dict[str, Any]) -> ControlTableEvidencePackage:
    """Load and redact control-table evidence from JSON/YAML-compatible data."""

    if isinstance(path, dict):
        payload = path
    else:
        source = Path(path)
        payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Control-table evidence must be a JSON object.")

    redacted = redact_secrets(payload)
    scope_payload = _mapping(redacted.get("scope"))
    return ControlTableEvidencePackage(
        scope=ControlTableScope(
            catalog=_optional_str(scope_payload.get("catalog")),
            ctrl_schema=_optional_str(scope_payload.get("ctrl_schema")),
            target_table=_optional_str(scope_payload.get("target_table")),
            layer=_optional_str(scope_payload.get("layer")),
            domain=_optional_str(scope_payload.get("domain")),
            window=_optional_str(scope_payload.get("window")),
            platform=_optional_str(scope_payload.get("platform")),
            evidence_store=_optional_str(scope_payload.get("evidence_store") or scope_payload.get("store")),
            database=_optional_str(scope_payload.get("database") or scope_payload.get("schema")),
        ),
        runs=_section(redacted, "runs"),
        errors=_section(redacted, "errors"),
        quality=_section(redacted, "quality"),
        quarantine=_section(redacted, "quarantine"),
        streams=_section(redacted, "streams"),
        schema_changes=_section(redacted, "schema_changes"),
        lineage=_section(redacted, "lineage"),
        metadata=_section(redacted, "metadata"),
        annotations=_section(redacted, "annotations"),
        access=_section(redacted, "access"),
        operations=_section(redacted, "operations"),
        cost=_section(redacted, "cost"),
        state=_section(redacted, "state"),
        locks=_section(redacted, "locks"),
        collection_errors=_list_of_mappings(redacted.get("collection_errors")),
    )


def analyze_control_tables(path: str | Path | dict[str, Any] | ControlTableEvidencePackage) -> ControlTableAnalysis:
    """Analyze ContractForge operational evidence and return deterministic findings."""

    evidence = path if isinstance(path, ControlTableEvidencePackage) else load_control_table_evidence(path)
    metrics = _metrics(evidence)
    findings = [
        *_status_findings(evidence, metrics),
        *_failure_cluster_findings(evidence, metrics),
        *_duration_findings(evidence, metrics),
        *_quality_findings(evidence, metrics),
        *_schema_findings(evidence, metrics),
        *_stream_findings(evidence, metrics),
        *_governance_findings(evidence, metrics),
        *_cost_findings(evidence, metrics),
        *_state_findings(evidence, metrics),
        *_coverage_findings(evidence, metrics),
        *_freshness_findings(evidence),
        *_collection_findings(evidence),
    ]
    risk = _max_risk([finding.severity for finding in findings])
    status = "PASS" if not findings else "FAIL" if risk in {"critical", "high"} else "WARN"
    recommendations = _recommendations(findings)
    follow_up = _follow_up_queries(evidence)
    summary = _summary(status, metrics, findings)

    return ControlTableAnalysis(
        status=status,
        risk=risk,
        summary=summary,
        metrics=metrics,
        findings=findings,
        recommendations=recommendations,
        follow_up_queries=follow_up,
        traceability=Traceability(
            confidence=0.88 if evidence.runs else 0.50,
            evidence=[
                EvidenceItem(
                    source="evidence_model",
                    path=evidence.scope.target_table,
                    reason="Analyzed redacted ContractForge evidence model data.",
                    value={
                        "platform": evidence.scope.platform,
                        "evidence_store": evidence.scope.evidence_store,
                        "runs": len(evidence.runs),
                        "errors": len(evidence.errors),
                        "quality": len(evidence.quality),
                        "quarantine": len(evidence.quarantine),
                        "streams": len(evidence.streams),
                    },
                    confidence=0.88 if evidence.runs else 0.50,
                )
            ],
            review_required=bool(findings),
        ),
    )


def _metrics(evidence: ControlTableEvidencePackage) -> dict[str, Any]:
    statuses = Counter(str(row.get("status") or "UNKNOWN").upper() for row in evidence.runs)
    failed_runs = sum(count for status, count in statuses.items() if status in {"FAILED", "FAIL", "ERROR"})
    durations = [_float(row.get("duration_seconds") or row.get("execution_seconds") or row.get("total_duration_seconds")) for row in evidence.runs]
    durations = [value for value in durations if value is not None]
    rows_written = [_float(row.get("rows_written") or row.get("total_rows_written")) for row in evidence.runs]
    rows_written = [value for value in rows_written if value is not None]
    quality_failed = sum(1 for row in evidence.quality if str(row.get("status") or row.get("quality_status") or "").upper() in {"FAILED", "FAIL"})
    quarantined = sum(_float(row.get("rows_quarantined") or row.get("failed_count")) or 0 for row in evidence.quality)
    quarantine_records = len(evidence.quarantine)
    schema_drift = sum(1 for row in evidence.schema_changes if str(row.get("change_type") or row.get("status") or "").upper() not in {"", "NONE", "NO_CHANGE"})
    stream_batches = sum(_float(row.get("batches_processed")) or 0 for row in evidence.streams)
    stream_rows_written = sum(_float(row.get("total_rows_written") or row.get("rows_written")) or 0 for row in evidence.streams)
    failure_clusters = _failure_clusters(evidence.runs)
    access_failures = _status_count(evidence.access, {"FAILED", "FAIL", "ERROR"})
    annotation_failures = _status_count(evidence.annotations, {"FAILED", "FAIL", "ERROR"})
    lineage_events = len(evidence.lineage)
    cost_signals = len(evidence.cost)
    estimated_cost = sum(_float(row.get("estimated_compute_cost") or row.get("estimated_cost") or row.get("signal_value")) or 0 for row in evidence.cost)
    state_targets = sorted({str(row.get("target_table")) for row in evidence.state if row.get("target_table")})
    evidence_sections = _present_sections(evidence)

    return {
        "platform": evidence.scope.platform,
        "evidence_store": evidence.scope.evidence_store,
        "evidence_sections_present": evidence_sections,
        "evidence_sections_missing": _missing_evidence_sections(evidence_sections),
        "runs_total": len(evidence.runs),
        "runs_failed": failed_runs,
        "run_success_rate": _ratio(len(evidence.runs) - failed_runs, len(evidence.runs)),
        "status_counts": dict(statuses),
        "duration_seconds_median": median(durations) if durations else None,
        "duration_seconds_max": max(durations) if durations else None,
        "rows_written_total": sum(rows_written),
        "quality_failed_checks": quality_failed,
        "rows_quarantined_total": quarantined,
        "quarantine_records_total": quarantine_records,
        "schema_change_events": schema_drift,
        "stream_batches_processed": stream_batches,
        "stream_rows_written_total": stream_rows_written,
        "lineage_events_total": lineage_events,
        "access_failures": access_failures,
        "annotation_failures": annotation_failures,
        "cost_signals_total": cost_signals,
        "estimated_cost_total": round(estimated_cost, 6) if cost_signals else None,
        "state_targets": state_targets,
        "error_categories": dict(_error_categories(evidence.errors)),
        "failure_clusters": dict(failure_clusters),
        "target_tables": sorted({str(row.get("target_table")) for row in evidence.runs if row.get("target_table")}),
        "connectors": sorted({str(row.get("source_connector") or row.get("connector")) for row in evidence.runs if row.get("source_connector") or row.get("connector")}),
        "runtimes": sorted({str(row.get("runtime_type") or row.get("runtime")) for row in evidence.runs if row.get("runtime_type") or row.get("runtime")}),
    }


def _status_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    del evidence
    failed = int(metrics["runs_failed"])
    total = int(metrics["runs_total"])
    if total and failed / total >= 0.50:
        return [
            _finding(
                code="observability.failure_rate.high",
                severity="high",
                title="High failure rate",
                detail=f"{failed} of {total} analyzed runs failed.",
                recommendation="Group failures by connector, target table and error category before approving more runs.",
            )
        ]
    if failed:
        return [
            _finding(
                code="observability.failure_rate.nonzero",
                severity="medium",
                title="Recent run failures detected",
                detail=f"{failed} of {total} analyzed runs failed.",
                recommendation="Review failing run IDs and compare with recent contract, connector or runtime changes.",
            )
        ]
    return []


def _duration_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    durations_by_table: dict[str, list[float]] = defaultdict(list)
    for row in evidence.runs:
        table = str(row.get("target_table") or "unknown")
        value = _float(row.get("duration_seconds") or row.get("execution_seconds") or row.get("total_duration_seconds"))
        if value is not None:
            durations_by_table[table].append(value)

    findings: list[Finding] = []
    for table, durations in durations_by_table.items():
        if len(durations) < 3:
            continue
        med = median(durations)
        latest = durations[-1]
        if med > 0 and latest >= med * 3:
            findings.append(
                _finding(
                    code="observability.duration.outlier",
                    severity="medium",
                    title="Run duration outlier",
                    detail=f"Latest duration for {table} is {latest:.1f}s, at least 3x median {med:.1f}s.",
                    recommendation="Inspect stage durations, source latency, target table size and cluster/runtime changes.",
                    path=table,
                )
            )
    if metrics.get("duration_seconds_max") and metrics.get("duration_seconds_median"):
        if metrics["duration_seconds_max"] >= metrics["duration_seconds_median"] * 4:
            findings.append(
                _finding(
                    code="observability.duration.spread",
                    severity="low",
                    title="Wide duration spread",
                    detail="Maximum run duration is at least 4x the median duration.",
                    recommendation="Segment latency by connector, write mode and target table to isolate instability.",
                )
            )
    return findings


def _failure_cluster_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    clusters = metrics.get("failure_clusters") or {}
    recurring = {cluster: count for cluster, count in clusters.items() if count >= 2}
    if recurring:
        largest_cluster, largest_count = max(recurring.items(), key=lambda item: item[1])
        findings.append(
            _finding(
                code="observability.failure.cluster.recurring",
                severity="high",
                title="Recurring failure cluster detected",
                detail=f"Failure cluster {largest_cluster!r} occurred {largest_count} time(s).",
                recommendation="Prioritize the repeated target/runtime/connector combination before investigating isolated failures.",
            )
        )

    error_categories = metrics.get("error_categories") or {}
    category_findings = {
        "auth": (
            "observability.error.auth_recurring",
            "Recurring authentication or authorization failures",
            "Review secret references, Unity Catalog permissions, external locations and provider credentials.",
        ),
        "network": (
            "observability.error.network_recurring",
            "Recurring network or egress failures",
            "Review serverless network policy, DNS resolution, allowed endpoints and connector egress requirements.",
        ),
        "dependency": (
            "observability.error.dependency_recurring",
            "Recurring dependency or driver failures",
            "Review cluster libraries, serverless-supported dependencies and connector installation requirements.",
        ),
    }
    for category, count in error_categories.items():
        if count < 2 or category not in category_findings:
            continue
        code, title, recommendation = category_findings[category]
        findings.append(
            _finding(
                code=code,
                severity="high",
                title=title,
                detail=f"Error category {category!r} appeared {count} time(s).",
                recommendation=recommendation,
            )
        )

    runtimes = metrics.get("runtimes") or []
    if len(runtimes) > 1 and metrics.get("runs_failed"):
        findings.append(
            _finding(
                code="observability.runtime.mixed_failures",
                severity="medium",
                title="Failures span multiple runtime types",
                detail=f"Evidence includes runtime types: {', '.join(runtimes)}.",
                recommendation="Compare serverless and classic behavior separately before attributing failures to the contract.",
            )
        )
    return findings


def _quality_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if metrics["quality_failed_checks"]:
        findings.append(
            _finding(
                code="observability.quality.failures",
                severity="high",
                title="Quality failures detected",
                detail=f"{metrics['quality_failed_checks']} quality check(s) failed.",
                recommendation="Inspect failing rules, quarantine volume and whether rules need stricter ownership or source remediation.",
            )
        )
    if metrics["rows_quarantined_total"]:
        findings.append(
            _finding(
                code="observability.quality.quarantine",
                severity="medium",
                title="Rows were quarantined",
                detail=f"{metrics['rows_quarantined_total']} row(s) were quarantined across analyzed quality evidence.",
                recommendation="Review quarantined rows by rule and decide whether to fix source data, adjust rule thresholds or reprocess.",
            )
        )
    if evidence.quarantine and not metrics["rows_quarantined_total"]:
        findings.append(
            _finding(
                code="observability.quality.quarantine_unlinked",
                severity="low",
                title="Quarantine records exist without run-level quarantine counts",
                detail=f"{len(evidence.quarantine)} quarantine row(s) were present but quality/run metrics did not report rows_quarantined.",
                recommendation="Ensure adapters populate rows_quarantined on runs or failed_count on quality evidence for dashboard parity.",
            )
        )
    return findings


def _schema_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    del evidence
    if metrics["schema_change_events"]:
        return [
            _finding(
                code="observability.schema.drift",
                severity="medium",
                title="Schema change events detected",
                detail=f"{metrics['schema_change_events']} schema change event(s) were found.",
                recommendation="Review expected schema evolution policy and confirm changes were intentional before downstream consumption.",
            )
        ]
    return []


def _stream_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for row in evidence.streams:
        batches = _float(row.get("batches_processed")) or 0
        rows_written = _float(row.get("total_rows_written") or row.get("rows_written")) or 0
        status = str(row.get("status") or "").upper()
        if status == "SUCCESS" and batches == 0 and rows_written > 0:
            findings.append(
                _finding(
                    code="observability.stream.metrics_inconsistent",
                    severity="high",
                    title="Stream metrics are inconsistent",
                    detail="A successful stream reports zero batches but non-zero written rows.",
                    recommendation="Reconcile stream finish metrics with child batch runs and ctrl_ingestion_streams aggregation.",
                )
            )
    if metrics["stream_batches_processed"] and metrics["stream_rows_written_total"] == 0:
        findings.append(
            _finding(
                code="observability.stream.zero_output",
                severity="medium",
                title="Stream processed batches without output rows",
                detail="Streams processed microbatches but reported zero rows written.",
                recommendation="Confirm source availability, checkpoint state, filters and child run metrics.",
            )
        )
    return findings


def _governance_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    del evidence
    findings: list[Finding] = []
    governance_rules = (
        ("access_failures", "observability.governance.access_failed", "Access application failures detected", "Review grants, row filters, masks and platform governance permissions."),
        ("annotation_failures", "observability.governance.annotations_failed", "Annotation application failures detected", "Review table/column metadata permissions and adapter annotation SQL/API output."),
    )
    for metric, code, title, recommendation in governance_rules:
        count = int(metrics.get(metric) or 0)
        if not count:
            continue
        findings.append(
            _finding(
                code=code,
                severity="high" if metric == "access_failures" else "medium",
                title=title,
                detail=f"{count} governance evidence row(s) failed.",
                recommendation=recommendation,
            )
        )
    return findings


def _cost_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    del evidence
    if metrics.get("cost_signals_total"):
        return []
    return [
        _finding(
            code="observability.cost.missing",
            severity="low",
            title="Cost signal evidence is missing",
            detail="No cost signal rows were included in the evidence package.",
            recommendation="Populate ctrl_ingestion_cost or adapter-equivalent cost evidence so cost regressions can be reviewed.",
        )
    ]


def _state_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    del metrics
    findings: list[Finding] = []
    stale_state = [
        row
        for row in evidence.state
        if str(row.get("last_status") or row.get("status") or "").upper() in {"FAILED", "FAIL", "ERROR"}
    ]
    if stale_state:
        findings.append(
            _finding(
                code="observability.state.last_status_failed",
                severity="medium",
                title="State table points to failed last status",
                detail=f"{len(stale_state)} state row(s) report failed last status.",
                recommendation="Confirm recovery behavior and watermark/state consistency before relying on incremental continuation.",
            )
        )
    return findings


def _coverage_findings(evidence: ControlTableEvidencePackage, metrics: dict[str, Any]) -> list[Finding]:
    if not evidence.runs:
        return []
    missing = set(metrics.get("evidence_sections_missing") or ())
    required_for_observability = {"errors", "quality", "state"}
    missing_required = sorted(missing & required_for_observability)
    if not missing_required:
        return []
    return [
        _finding(
            code="observability.evidence.coverage_partial",
            severity="low",
            title="Evidence package omits core observability sections",
            detail=f"Missing evidence sections: {', '.join(missing_required)}.",
            recommendation="Collect all core evidence sections from Databricks control tables or AWS Iceberg/Athena evidence tables for complete analysis.",
        )
    ]


def _freshness_findings(evidence: ControlTableEvidencePackage) -> list[Finding]:
    findings: list[Finding] = []
    for row in evidence.operations:
        sla = _float(row.get("freshness_sla_minutes") or row.get("sla_minutes"))
        lag = _float(row.get("minutes_since_last_success") or row.get("freshness_lag_minutes"))
        table = str(row.get("target_table") or row.get("table") or "unknown")
        if sla is None or lag is None or lag <= sla:
            continue
        findings.append(
            _finding(
                code="observability.freshness.sla_breach",
                severity="high",
                title="Freshness SLA breach detected",
                detail=f"{table} has freshness lag {lag:.1f} minutes above SLA {sla:.1f} minutes.",
                recommendation="Prioritize upstream availability, job schedule, recent failures and recovery/backfill plan.",
                path=table,
            )
        )
    return findings


def _collection_findings(evidence: ControlTableEvidencePackage) -> list[Finding]:
    if not evidence.collection_errors:
        return []
    return [
        _finding(
            code="observability.collection.partial",
            severity="medium",
            title="Evidence collection was partial",
            detail=f"{len(evidence.collection_errors)} collection error(s) were reported.",
            recommendation="Resolve missing control tables or permissions before relying on aggregate operational analysis.",
        )
    ]


def _error_categories(errors: list[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in errors:
        text = " ".join(str(value) for value in row.values() if value is not None).lower()
        if any(term in text for term in ("permission", "unauthorized", "forbidden", "403")):
            counter["auth"] += 1
        elif any(term in text for term in ("dns", "network", "egress", "timeout")):
            counter["network"] += 1
        elif any(term in text for term in ("schema", "cannot resolve", "type", "column")):
            counter["schema"] += 1
        elif any(term in text for term in ("quality", "quarantine", "not_null")):
            counter["quality"] += 1
        elif any(term in text for term in ("module", "driver", "classnotfound", "library")):
            counter["dependency"] += 1
        else:
            counter["unknown"] += 1
    return counter


def _failure_clusters(runs: list[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in runs:
        status = str(row.get("status") or "").upper()
        if status not in {"FAILED", "FAIL", "ERROR"}:
            continue
        target = row.get("target_table") or "unknown_target"
        connector = row.get("source_connector") or row.get("connector") or "unknown_connector"
        runtime = row.get("runtime_type") or row.get("runtime") or "unknown_runtime"
        counter[f"{target}|{connector}|{runtime}"] += 1
    return counter


def _recommendations(findings: list[Finding]) -> list[str]:
    result: list[str] = []
    for finding in findings:
        if finding.recommendation not in result:
            result.append(finding.recommendation)
    return result


def _follow_up_queries(evidence: ControlTableEvidencePackage) -> list[str]:
    scope = evidence.scope
    target_filter = f" WHERE target_table = '{scope.target_table}'" if scope.target_table else ""
    prefix = _query_table_prefix(scope)
    return [
        f"SELECT status, count(*) FROM {prefix}ctrl_ingestion_runs{target_filter} GROUP BY status ORDER BY count(*) DESC",
        f"SELECT target_table, max(duration_seconds), avg(duration_seconds) FROM {prefix}ctrl_ingestion_runs{target_filter} GROUP BY target_table",
        f"SELECT rule_name, status, count(*) FROM {prefix}ctrl_ingestion_quality{target_filter} GROUP BY rule_name, status",
        f"SELECT target_table, count(*) FROM {prefix}ctrl_ingestion_quarantine{target_filter} GROUP BY target_table",
        f"SELECT target_table, sum(signal_value) FROM {prefix}ctrl_ingestion_cost{target_filter} GROUP BY target_table",
    ]


def _summary(status: str, metrics: dict[str, Any], findings: list[Finding]) -> str:
    return (
        f"{status}: analyzed {metrics['runs_total']} run(s), {metrics['runs_failed']} failed run(s), "
        f"{metrics['quality_failed_checks']} quality failure(s), {len(findings)} finding(s)."
    )


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
                source="evidence_model",
                path=path,
                reason=f"Deterministic observability rule {code!r} identified this condition.",
                confidence=1.0,
            )
        ],
    )


def _section(payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
    aliases = _section_aliases(name)
    for alias in aliases:
        rows = _list_of_mappings(payload.get(alias))
        if rows:
            return rows
    return []


def _section_aliases(name: str) -> tuple[str, ...]:
    aliases = [name]
    table = EVIDENCE_TABLES.get(name) or STATE_TABLES.get(name)
    if table:
        aliases.append(table)
    aliases.extend((f"aws_{name}", f"databricks_{name}", f"iceberg_{name}", f"athena_{name}"))
    return tuple(dict.fromkeys(aliases))


def _present_sections(evidence: ControlTableEvidencePackage) -> list[str]:
    section_rows = {
        "runs": evidence.runs,
        "errors": evidence.errors,
        "quality": evidence.quality,
        "quarantine": evidence.quarantine,
        "streams": evidence.streams,
        "schema_changes": evidence.schema_changes,
        "lineage": evidence.lineage,
        "metadata": evidence.metadata,
        "annotations": evidence.annotations,
        "access": evidence.access,
        "operations": evidence.operations,
        "cost": evidence.cost,
        "state": evidence.state,
        "locks": evidence.locks,
    }
    return sorted(name for name, rows in section_rows.items() if rows)


def _missing_evidence_sections(present: list[str]) -> list[str]:
    expected = set(EVIDENCE_TABLES) | set(STATE_TABLES)
    optional = {"explain", "locks", "metadata", "annotations", "access", "lineage", "streams", "schema_changes", "quarantine", "cost", "operations"}
    return sorted((expected - optional) - set(present))


def _status_count(rows: list[dict[str, Any]], statuses: set[str]) -> int:
    return sum(1 for row in rows if str(row.get("status") or "").upper() in statuses)


def _query_table_prefix(scope: ControlTableScope) -> str:
    if scope.platform == "aws" or scope.evidence_store in {"iceberg", "athena"}:
        return f"glue_catalog.{scope.database}." if scope.database else ""
    if scope.catalog and scope.ctrl_schema:
        return f"{scope.catalog}.{scope.ctrl_schema}."
    return f"{scope.database}." if scope.database else ""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _optional_str(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return round(float(numerator) / float(denominator), 4) if denominator else None


def _severity_rank(severity: Severity) -> int:
    return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[severity]


def _max_risk(severities: list[Severity]) -> Severity:
    return max(severities, key=_severity_rank) if severities else "info"
