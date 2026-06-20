"""Human-facing Markdown and HTML reports for ContractForge AI workflows."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import Any

from contractforge_ai.enrichment import EnrichmentResult


@dataclass(frozen=True)
class RenderedReport:
    """A report rendered in both human-facing formats."""

    markdown: str
    html: str


def render_guided_project_review(
    guided_result: Any,
    *,
    enrichments: dict[str, EnrichmentResult | dict[str, Any]] | None = None,
    consolidated_artifacts: list[Any] | None = None,
    title: str = "ContractForge AI Project Review",
) -> RenderedReport:
    """Render a single review report for a guided project generation result."""

    markdown = _guided_project_markdown(
        guided_result,
        enrichments=enrichments,
        consolidated_artifacts=consolidated_artifacts,
        title=title,
    )
    return RenderedReport(
        markdown=markdown,
        html=_guided_project_html(
            title=title,
            guided_result=guided_result,
            enrichments=enrichments,
            consolidated_artifacts=consolidated_artifacts,
        ),
    )


def render_operational_analysis_review(
    analysis: Any,
    *,
    enrichment: EnrichmentResult | dict[str, Any] | None = None,
    title: str = "ContractForge AI Operational Review",
) -> RenderedReport:
    """Render one review report for deterministic and AI-enriched operational analysis."""

    markdown = _operational_markdown(analysis, enrichment=enrichment, title=title)
    return RenderedReport(
        markdown=markdown,
        html=_operational_html(title=title, analysis=analysis, enrichment=enrichment),
    )


def render_markdown_report(markdown: str, *, title: str) -> RenderedReport:
    """Render existing Markdown into the standard ContractForge AI report shell."""

    return RenderedReport(markdown=markdown, html=_html_page(title, markdown))


def render_project_plan_review(
    project: Any,
    *,
    title: str | None = None,
) -> RenderedReport:
    """Render a rich review report for deterministic project plans.

    This is used for direct project generation where there is no guided or
    intent-first result object, but users still need the same review-quality
    HTML surface as AI-assisted workflows.
    """

    display_title = title or f"{getattr(project, 'name', 'ContractForge')} Project Review"
    markdown = getattr(project, "to_markdown")()
    return RenderedReport(
        markdown=markdown,
        html=_project_plan_html(display_title, project),
    )


def render_project_structure_review(
    report: Any,
    *,
    title: str = "ContractForge Project Structure Validation",
) -> RenderedReport:
    """Render a rich validation report for a real ContractForge project folder."""

    markdown = _project_structure_markdown(report, title=title)
    return RenderedReport(
        markdown=markdown,
        html=_project_structure_html(title, report),
    )


def render_intent_generation_review(
    *,
    project: Any,
    request: Any,
    schema_source: dict[str, Any],
    intent: Any,
    project_state: Any,
    gap_plan: Any,
    transformation_plan: Any,
    context_snapshot: Any,
    generation_signature: Any,
    policy_result: Any,
    audit_trail: Any,
    provider_proposal_audit: Any = None,
    transformation_enrichment: EnrichmentResult | None = None,
    pre_generation_enrichment: EnrichmentResult | None = None,
    enrichment: EnrichmentResult | None = None,
    title: str = "ContractForge AI Generation Review",
) -> RenderedReport:
    """Render a polished review report for intent-first project generation."""

    markdown = _intent_generation_markdown(
        project=project,
        request=request,
        schema_source=schema_source,
        intent=intent,
        project_state=project_state,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
        context_snapshot=context_snapshot,
        generation_signature=generation_signature,
        policy_result=policy_result,
        audit_trail=audit_trail,
        provider_proposal_audit=provider_proposal_audit,
        transformation_enrichment=transformation_enrichment,
        pre_generation_enrichment=pre_generation_enrichment,
        enrichment=enrichment,
        title=title,
    )
    html_report = _intent_generation_html(
        title=title,
        project=project,
        request=request,
        schema_source=schema_source,
        intent=intent,
        project_state=project_state,
        gap_plan=gap_plan,
        transformation_plan=transformation_plan,
        context_snapshot=context_snapshot,
        generation_signature=generation_signature,
        policy_result=policy_result,
        audit_trail=audit_trail,
        provider_proposal_audit=provider_proposal_audit,
        transformation_enrichment=transformation_enrichment,
        pre_generation_enrichment=pre_generation_enrichment,
        enrichment=enrichment,
    )
    return RenderedReport(markdown=markdown, html=html_report)


def _guided_project_markdown(
    guided_result: Any,
    *,
    enrichments: dict[str, EnrichmentResult | dict[str, Any]] | None,
    consolidated_artifacts: list[Any] | None,
    title: str,
) -> str:
    project = getattr(guided_result, "project", None)
    planner = getattr(guided_result, "planner", None)
    context = getattr(guided_result, "context", None)
    validation = getattr(guided_result, "validation", None)
    critique = getattr(guided_result, "critique", None)
    spec_enrichment = getattr(guided_result, "spec_enrichment", None)
    governance = _guided_governance_payload(guided_result)

    lines = [
        f"# {title}",
        "",
        "## Executive Summary",
        "",
        f"- Status: `{getattr(guided_result, 'status', 'UNKNOWN')}`",
        f"- Selected target: `{getattr(guided_result, 'selected_target', None) or 'REVIEW_REQUIRED'}`",
        f"- Project: `{getattr(project, 'name', 'not generated') if project else 'not generated'}`",
        f"- Generated artifacts: `{len(getattr(project, 'artifacts', []) or [])}`",
        f"- Ready for deployment: `{str(bool(getattr(guided_result, 'ready', False))).lower()}`",
    ]
    if planner is not None:
        intent = getattr(planner, "intent", None)
        target = _target_name(intent)
        lines.extend(
            [
                "",
                "## Requested Project",
                "",
                f"- Connector: `{getattr(intent, 'connector', None) or 'REVIEW_REQUIRED'}`",
                f"- Source: `{getattr(intent, 'source_path', None) or 'REVIEW_REQUIRED'}`",
                f"- Target: `{target}`",
                f"- Layer: `{getattr(intent, 'layer', None) or 'REVIEW_REQUIRED'}`",
                f"- Write mode: `{getattr(intent, 'mode', None) or 'REVIEW_REQUIRED'}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Recommended Next Actions",
            "",
            "- Review all decisions required before deployment.",
            "- Review AI guidance as advisory input.",
            "- Validate generated contracts in the target Databricks workspace.",
            "- Replace compute, secret and workspace placeholders before running jobs.",
        ]
    )

    if project is not None:
        if project.report.decisions_required:
            lines.extend(["", "## Decisions Required Before Use", ""])
            for decision in project.report.decisions_required:
                location = f" `{decision.path}`" if decision.path else ""
                lines.append(f"-{location} {decision.question} - {decision.reason}")
        if project.report.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {item}" for item in project.report.warnings)

    provider_items: list[tuple[str, EnrichmentResult | dict[str, Any]]] = []
    if spec_enrichment is not None:
        provider_items.append(("Specification enrichment", spec_enrichment))
    if enrichments:
        provider_items.extend((str(name), enrichment) for name, enrichment in enrichments.items())
    if provider_items:
        lines.extend(["", "## AI Guidance", ""])
        for name, enrichment in provider_items:
            lines.extend(_enrichment_lines(name, enrichment))

    if consolidated_artifacts:
        lines.extend(
            [
                "",
                "## Consolidated Project Guide",
                "",
                "The generated project writes implementation files separately and keeps review guidance in this report.",
            ]
        )
        for artifact in consolidated_artifacts:
            lines.extend(_consolidated_artifact_lines(artifact))

    if validation is not None:
        lines.extend(["", "## Deterministic Validation", ""])
        lines.extend(_validation_lines(validation))

    if critique is not None:
        lines.extend(["", "## Critique", ""])
        lines.extend(_critique_lines(critique))

    if project is not None:
        lines.extend(["", "## Generated Artifacts", ""])
        for artifact in project.artifacts:
            lines.append(f"- `{artifact.path}` ({artifact.kind}){_suffix(artifact.description)}")

    if governance:
        lines.extend(["", "## Traceability", ""])
        lines.extend(_guided_compact_traceability_markdown(governance))

    if context is not None:
        lines.extend(
            [
                "",
                "## Context Evidence",
                "",
                f"- Runtime: `{context.runtime}`",
                f"- Context directory: `{context.context_dir or 'not provided'}`",
                f"- Explicit schema: `{context.schema_path or 'not provided'}`",
                f"- Files considered: `{len(context.files)}`",
                f"- Inferred schema: `{'yes' if context.inferred_schema else 'no'}`",
            ]
        )
        if context.files:
            lines.extend(["", "### Context Files", ""])
            for item in context.files:
                lines.append(f"- `{item.path}` ({item.format}, {item.size_bytes} bytes, records sampled: {item.records_sampled})")
    return "\n".join(lines).rstrip() + "\n"


def _project_structure_markdown(report: Any, *, title: str) -> str:
    lines = [
        f"# {title}",
        "",
        "## Executive Summary",
        "",
        f"- Status: `{getattr(report, 'status', 'UNKNOWN')}`",
        f"- Ready: `{str(bool(getattr(report, 'ready', False))).lower()}`",
        f"- Root: `{getattr(report, 'root', '')}`",
        f"- Summary: {getattr(report, 'summary', '')}",
    ]
    files = list(getattr(report, "files", []) or [])
    findings = list(getattr(report, "findings", []) or [])
    evidence = list(getattr(report, "evidence", []) or [])
    if files:
        lines.extend(["", "## Project Files", ""])
        for item in files:
            details = []
            if getattr(item, "adapter", None):
                details.append(f"adapter={item.adapter}")
            if getattr(item, "name", None):
                details.append(f"name={item.name}")
            suffix = f" ({', '.join(details)})" if details else ""
            lines.append(f"- `{_report_relative_path(item, report)}` - `{getattr(item, 'kind', 'file')}`{suffix}")
    if findings:
        lines.extend(["", "## Findings", ""])
        for finding in findings:
            path = f" `{finding.path}`" if getattr(finding, "path", None) else ""
            lines.extend(
                [
                    f"- `{finding.severity}` `{finding.code}`{path}: **{finding.title}**",
                    f"  - Detail: {finding.detail}",
                    f"  - Recommendation: {finding.recommendation}",
                ]
            )
    if evidence:
        lines.extend(["", "## Evidence", ""])
        for item in evidence:
            lines.append(item.to_markdown() if hasattr(item, "to_markdown") else f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def _project_structure_html(title: str, report: Any) -> str:
    files = list(getattr(report, "files", []) or [])
    findings = list(getattr(report, "findings", []) or [])
    evidence = list(getattr(report, "evidence", []) or [])
    status = str(getattr(report, "status", "UNKNOWN"))
    ready = bool(getattr(report, "ready", False))
    root = getattr(report, "root", "")
    summary = str(getattr(report, "summary", ""))
    severity_counts = _finding_severity_counts(findings)
    project_files = [item for item in files if getattr(item, "kind", None) == "project"]
    environment_files = [item for item in files if getattr(item, "kind", None) == "environment"]
    connection_files = [item for item in files if getattr(item, "kind", None) == "connection"]
    contract_files = [item for item in files if getattr(item, "kind", None) == "ingestion_bundle"]
    file_rows = [
        [
            getattr(item, "kind", "file"),
            _report_relative_path(item, report),
            getattr(item, "adapter", None) or "",
            getattr(item, "name", None) or "",
        ]
        for item in files
    ]
    analysis_rows = _project_structure_analysis_rows(status=status, ready=ready, findings=findings, evidence=evidence)
    raw_payload = html.escape(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>{_rich_report_css()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">A deterministic validation report for a real ContractForge project folder, including split contracts, shared connections, environments and adapter planning evidence.</p>
      <div class="badge-row">
        <span class="badge">Status: <span class="status-{html.escape(_status_class(status))}">{html.escape(status)}</span></span>
        <span class="badge">Ready: {html.escape(str(ready).lower())}</span>
        <span class="badge">Findings: {html.escape(str(len(findings)))}</span>
        <span class="badge">Evidence: {html.escape(str(len(evidence)))}</span>
      </div>
    </section>

    <section class="grid">
      {_metric_card("Project files", len(project_files), "Root project YAML files discovered and validated.")}
      {_metric_card("Environments", len(environment_files), "Environment YAML files available for adapter deployment.")}
      {_metric_card("Connections", len(connection_files), "Shared connector YAML files available for inheritance.")}
      {_metric_card("Contracts", len(contract_files), "Ingestion bundles discovered for deterministic validation.")}
    </section>

    <section class="two-col">
      <div class="section">
        <h2>Validation Result</h2>
        <div class="kv">
          <strong>Status</strong><span class="status-{html.escape(_status_class(status))}">{html.escape(status)}</span>
          <strong>Ready</strong><span>{html.escape(str(ready).lower())}</span>
          <strong>Root</strong><span><code>{html.escape(str(root))}</code></span>
          <strong>Summary</strong><span>{html.escape(summary)}</span>
        </div>
      </div>
      <div class="section">
        <h2>Finding Severity</h2>
        <div class="kv">
          <strong>Critical</strong><span class="risk-critical">{severity_counts["critical"]}</span>
          <strong>High</strong><span class="risk-high">{severity_counts["high"]}</span>
          <strong>Medium</strong><span class="risk-medium">{severity_counts["medium"]}</span>
          <strong>Low</strong><span class="risk-low">{severity_counts["low"]}</span>
        </div>
      </div>
    </section>

    {_table_section("Readiness Analysis", ["Signal", "Result", "Interpretation"], analysis_rows)}
    {_table_section("Project Files", ["Kind", "Path", "Adapter", "Name"], file_rows)}
    {_findings_section(findings)}
    {_evidence_section(evidence)}

    <section class="section">
      <h2>Raw Validation Payload</h2>
      <details class="guide-block">
        <summary>Show deterministic JSON payload</summary>
        <pre><code>{raw_payload}</code></pre>
      </details>
    </section>
  </main>
</body>
</html>
"""


def _report_relative_path(item: Any, report: Any) -> str:
    root = getattr(report, "root", None)
    if root is not None and hasattr(item, "to_dict"):
        try:
            return str(item.to_dict(root=root).get("path") or getattr(item, "path", ""))
        except Exception:
            pass
    return str(getattr(item, "path", ""))


def _finding_severity_counts(findings: list[Any]) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in findings:
        severity = str(getattr(finding, "severity", "")).lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def _project_structure_analysis_rows(*, status: str, ready: bool, findings: list[Any], evidence: list[Any]) -> list[list[str]]:
    critical_or_high = [
        finding
        for finding in findings
        if str(getattr(finding, "severity", "")).lower() in {"critical", "high"}
    ]
    medium = [
        finding
        for finding in findings
        if str(getattr(finding, "severity", "")).lower() == "medium"
    ]
    adapter_evidence = [
        item
        for item in evidence
        if str(getattr(item, "source", "")).startswith("contractforge_")
        or str(getattr(item, "source", "")).startswith("adapter.")
    ]
    readiness = (
        "Deployable validation gate with warnings"
        if status == "READY_WITH_WARNINGS"
        else "Deployable validation gate"
        if ready
        else "Not deployable without user action"
    )
    return [
        [
            "Readiness",
            status,
            readiness,
        ],
        [
            "Blocking findings",
            str(len(critical_or_high)),
            "Critical and high findings block readiness. Medium findings are warnings unless the project policy chooses to fail on them.",
        ],
        [
            "Warnings",
            str(len(medium)),
            "Warnings preserve real adapter boundaries without marking known-success projects as incomplete.",
        ],
        [
            "Adapter planning",
            str(len(adapter_evidence)),
            "Adapter checks are deterministic and do not execute Databricks, AWS, or other platform SDK operations.",
        ],
    ]


def _compact_report_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        text = str(value)
    if len(text) > 240:
        return text[:237].rstrip() + "..."
    return text


def _findings_section(findings: list[Any]) -> str:
    if not findings:
        return '<section class="section"><h2>Findings</h2><p>No findings for this section.</p></section>'
    cards = []
    for finding in findings:
        severity = str(getattr(finding, "severity", "unknown"))
        code = str(getattr(finding, "code", "unknown"))
        title = str(getattr(finding, "title", "Finding"))
        path = str(getattr(finding, "path", "") or "")
        detail = str(getattr(finding, "detail", ""))
        recommendation = str(getattr(finding, "recommendation", ""))
        cards.append(
            '<article class="finding-card">'
            '<div class="finding-head">'
            f'<span class="severity-pill status-{html.escape(_status_class(severity))}">{html.escape(severity.upper())}</span>'
            f"<code>{html.escape(code)}</code>"
            "</div>"
            f"<h3>{html.escape(title)}</h3>"
            f'{_finding_path(path)}'
            '<div class="finding-grid">'
            f"<div><strong>Detail</strong><p>{html.escape(detail)}</p></div>"
            f"<div><strong>Recommendation</strong><p>{html.escape(recommendation)}</p></div>"
            "</div>"
            "</article>"
        )
    return (
        '<section class="section">'
        "<h2>Findings</h2>"
        '<div class="finding-list">'
        f"{''.join(cards)}"
        "</div>"
        "</section>"
    )


def _evidence_section(evidence: list[Any]) -> str:
    if not evidence:
        return '<section class="section"><h2>Evidence And Adapter Planning</h2><p>No evidence for this section.</p></section>'
    cards = []
    for item in evidence:
        source = str(getattr(item, "source", "unknown"))
        path = str(getattr(item, "path", "") or "")
        reason = str(getattr(item, "reason", ""))
        confidence = getattr(item, "confidence", None)
        value = getattr(item, "value", None)
        planning_status = _planning_status(value)
        status_html = (
            f'<span class="severity-pill status-{html.escape(_status_class(planning_status))}">{html.escape(planning_status)}</span>'
            if planning_status
            else ""
        )
        value_html = f"<pre><code>{html.escape(_compact_report_value(value))}</code></pre>" if value is not None else ""
        cards.append(
            '<article class="evidence-card">'
            '<div class="finding-head">'
            f"<strong>{html.escape(source)}</strong>"
            f"{status_html}"
            "</div>"
            f'{_finding_path(path)}'
            '<div class="finding-grid">'
            f"<div><strong>Reason</strong><p>{html.escape(reason)}</p></div>"
            f"<div><strong>Confidence</strong><p>{html.escape('not provided' if confidence is None else str(confidence))}</p></div>"
            "</div>"
            f"{value_html}"
            "</article>"
        )
    return (
        '<section class="section">'
        "<h2>Evidence And Adapter Planning</h2>"
        '<div class="finding-list">'
        f"{''.join(cards)}"
        "</div>"
        "</section>"
    )


def _planning_status(value: Any) -> str:
    if isinstance(value, dict):
        status = value.get("planning_status")
        if status:
            return str(status)
    return ""


def _finding_path(path: str) -> str:
    if not path:
        return ""
    return f'<div class="finding-path"><strong>Path</strong><code>{html.escape(path)}</code></div>'


def _project_plan_html(title: str, project: Any) -> str:
    artifacts = list(getattr(project, "artifacts", []) or [])
    report = getattr(project, "report", None)
    traceability = getattr(project, "traceability", None)
    decisions = list(getattr(report, "decisions_required", []) or []) if report is not None else []
    warnings = list(getattr(report, "warnings", []) or []) if report is not None else []
    assumptions = list(getattr(report, "assumptions", []) or []) if report is not None else []
    if traceability is not None:
        assumptions.extend(list(getattr(traceability, "assumptions", []) or []))
    evidence = list(getattr(traceability, "evidence", []) or []) if traceability is not None else []
    traceability_decisions = list(getattr(traceability, "decisions_required", []) or []) if traceability is not None else []
    all_decisions = [*decisions, *traceability_decisions]
    project_name = getattr(project, "name", "not generated")
    target = getattr(project, "target", "unknown")
    confidence = getattr(traceability, "confidence", None) if traceability is not None else None
    confidence_label = getattr(traceability, "confidence_level", "unknown") if traceability is not None else "unknown"
    review_required = getattr(traceability, "review_required", bool(all_decisions)) if traceability is not None else bool(all_decisions)
    ready = not all_decisions and not warnings and not review_required
    summary = getattr(report, "summary", "Generated project plan.") if report is not None else "Generated project plan."

    artifact_rows = [[artifact.path, artifact.kind, artifact.description or "generated artifact"] for artifact in artifacts]
    decision_rows = [[decision.path or "review", decision.question, decision.reason] for decision in all_decisions]
    warning_rows = [[item] for item in warnings]
    assumption_rows = [[item.statement, item.confidence, item.review_required] for item in assumptions]
    evidence_rows = [
        [item.source, item.path or "", item.reason, "" if item.confidence is None else item.confidence]
        for item in evidence
    ]
    markdown_body = _markdown_to_html(getattr(project, "to_markdown")())
    status = "READY" if ready else "NEEDS_DECISIONS"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>{_rich_report_css()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">A deterministic ContractForge project review with generated files, required decisions, assumptions, traceability evidence and deployment readiness signals.</p>
      <div class="badge-row">
        <span class="badge">Status: <span class="status-{html.escape(_status_class(status))}">{html.escape(status)}</span></span>
        <span class="badge">Project: {html.escape(str(project_name))}</span>
        <span class="badge">Target: {html.escape(str(target))}</span>
        <span class="badge">Ready: {html.escape(str(ready).lower())}</span>
      </div>
    </section>

    <section class="grid">
      {_metric_card("Artifacts", len(artifacts), "Implementation and review artifacts generated for this project.")}
      {_metric_card("Decisions", len(all_decisions), "Open decisions before this output should be treated as deployable.")}
      {_metric_card("Warnings", len(warnings), "Warnings attached to the generated project plan.")}
      {_metric_card("Evidence", len(evidence), "Traceability evidence items supporting this project output.")}
    </section>

    <section class="two-col">
      <div class="section">
        <h2>Generated Project</h2>
        <div class="kv">
          <strong>Name</strong><span>{html.escape(str(project_name))}</span>
          <strong>Target</strong><span>{html.escape(str(target))}</span>
          <strong>Summary</strong><span>{html.escape(str(summary))}</span>
        </div>
      </div>
      <div class="section">
        <h2>Review Signal</h2>
        <div class="kv">
          <strong>Confidence</strong><span>{html.escape(str(confidence_label))}{' (' + html.escape(str(confidence)) + ')' if confidence is not None else ''}</span>
          <strong>Review required</strong><span>{html.escape(str(review_required).lower())}</span>
          <strong>Artifact count</strong><span>{html.escape(str(len(artifacts)))}</span>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Recommended Next Actions</h2>
      <div class="callout">Review all decisions and warnings, verify environment-specific placeholders, then run deterministic validation and adapter planning before deployment.</div>
    </section>

    {_table_section("Decisions Required Before Use", ["Path", "Question", "Reason"], decision_rows)}
    {_table_section("Project Warnings", ["Warning"], warning_rows)}
    {_table_section("Assumptions", ["Statement", "Confidence", "Review required"], assumption_rows)}
    {_table_section("Traceability Evidence", ["Source", "Path", "Reason", "Confidence"], evidence_rows)}
    {_table_section("Generated Artifacts", ["Path", "Kind", "Description"], artifact_rows)}

    <section class="section">
      <h2>Consolidated Project Plan</h2>
      {markdown_body}
    </section>
  </main>
</body>
</html>
"""


def _guided_project_html(
    *,
    title: str,
    guided_result: Any,
    enrichments: dict[str, EnrichmentResult | dict[str, Any]] | None,
    consolidated_artifacts: list[Any] | None,
) -> str:
    project = getattr(guided_result, "project", None)
    planner = getattr(guided_result, "planner", None)
    context = getattr(guided_result, "context", None)
    validation = getattr(guided_result, "validation", None)
    critique = getattr(guided_result, "critique", None)
    spec_enrichment = getattr(guided_result, "spec_enrichment", None)
    intent = getattr(planner, "intent", None)
    governance = _guided_governance_payload(guided_result)

    artifacts = list(getattr(project, "artifacts", []) or []) if project is not None else []
    report = getattr(project, "report", None)
    decisions = list(getattr(report, "decisions_required", []) or []) if report is not None else []
    warnings = list(getattr(report, "warnings", []) or []) if report is not None else []
    context_files = list(getattr(context, "files", []) or []) if context is not None else []
    validation_checks = list(getattr(validation, "checks", []) or []) if validation is not None else []
    validation_decisions = list(getattr(validation, "decisions_required", []) or []) if validation is not None else []
    critique_findings = list(getattr(critique, "findings", []) or []) if critique is not None else []
    critique_decisions = list(getattr(critique, "decisions_required", []) or []) if critique is not None else []
    consolidated = list(consolidated_artifacts or [])
    provider_items: list[tuple[str, EnrichmentResult | dict[str, Any]]] = []
    if spec_enrichment is not None:
        provider_items.append(("Specification enrichment", spec_enrichment))
    if enrichments:
        provider_items.extend((str(name), enrichment) for name, enrichment in enrichments.items())

    status = str(getattr(guided_result, "status", "UNKNOWN"))
    ready = bool(getattr(guided_result, "ready", False))
    selected_target = getattr(guided_result, "selected_target", None) or "REVIEW_REQUIRED"
    target = _target_name(intent)
    project_name = getattr(project, "name", None) or "not generated"
    source = getattr(intent, "source_path", None) or "REVIEW_REQUIRED"
    connector = getattr(intent, "connector", None) or "REVIEW_REQUIRED"
    layer = getattr(intent, "layer", None) or "REVIEW_REQUIRED"
    mode = getattr(intent, "mode", None) or "REVIEW_REQUIRED"

    artifact_rows = [[artifact.path, artifact.kind, artifact.description or "generated artifact"] for artifact in artifacts]
    decision_rows = [[decision.path or "review", decision.question, decision.reason] for decision in decisions]
    warning_rows = [[item] for item in warnings]
    context_rows = [
        [item.path, item.format, item.size_bytes, item.records_sampled]
        for item in context_files
    ]
    validation_rows = [
        [check.status, f"{check.kind}:{check.name}", check.summary]
        for check in validation_checks
    ]
    validation_decision_rows = _compact_review_decision_rows(validation_decisions)
    critique_rows = [
        [finding.severity, finding.code, finding.message]
        for finding in critique_findings
    ]
    critique_decision_rows = _compact_review_decision_rows(critique_decisions)
    provider_html = "\n".join(_provider_section_any(name, enrichment) for name, enrichment in provider_items)
    consolidated_html = _consolidated_html(consolidated)
    traceability_html = _guided_compact_traceability_html(governance)

    validation_status = getattr(validation, "status", "NOT_RUN") if validation is not None else "NOT_RUN"
    critique_status = getattr(critique, "status", "NOT_RUN") if critique is not None else "NOT_RUN"
    context_schema = getattr(context, "schema_path", None) if context is not None else None
    context_dir = getattr(context, "context_dir", None) if context is not None else None
    inferred_schema = bool(getattr(context, "inferred_schema", None)) if context is not None else False

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>{_rich_report_css()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">A single review surface for the interpreted request, generated project files, decisions, context evidence, deterministic validation, critique and AI guidance.</p>
      <div class="badge-row">
        <span class="badge">Status: <span class="status-{html.escape(_status_class(status))}">{html.escape(status)}</span></span>
        <span class="badge">Project: {html.escape(str(project_name))}</span>
        <span class="badge">Target: {html.escape(str(selected_target))}</span>
        <span class="badge">Ready: {html.escape(str(ready).lower())}</span>
      </div>
    </section>

    <section class="grid">
      {_metric_card("Artifacts", len(artifacts), "Implementation and review artifacts generated for this request.")}
      {_metric_card("Decisions", len(decisions) + len(validation_decisions) + len(critique_decisions), "Open decisions before this output should be treated as deployable.")}
      {_metric_card("Context files", len(context_files), "Files inspected to infer schema, examples or project context.")}
      {_metric_card("AI guidance", len(provider_items), "Advisory guidance blocks attached to this review.")}
    </section>

    <section class="two-col">
      <div class="section">
        <h2>Requested Project</h2>
        <div class="kv">
          <strong>Connector</strong><span>{html.escape(str(connector))}</span>
          <strong>Source</strong><span><code>{html.escape(str(source))}</code></span>
          <strong>Target</strong><span><code>{html.escape(str(target))}</code></span>
          <strong>Layer</strong><span>{html.escape(str(layer))}</span>
          <strong>Write mode</strong><span>{html.escape(str(mode))}</span>
        </div>
      </div>
      <div class="section">
        <h2>Evidence Snapshot</h2>
        <div class="kv">
          <strong>Runtime</strong><span>{html.escape(str(getattr(context, "runtime", "unknown") if context is not None else "unknown"))}</span>
          <strong>Context directory</strong><span><code>{html.escape(str(context_dir or "not provided"))}</code></span>
          <strong>Explicit schema</strong><span><code>{html.escape(str(context_schema or "not provided"))}</code></span>
          <strong>Inferred schema</strong><span>{html.escape("yes" if inferred_schema else "no")}</span>
          <strong>Validation</strong><span class="status-{html.escape(_status_class(validation_status))}">{html.escape(str(validation_status))}</span>
          <strong>Critique</strong><span class="status-{html.escape(_status_class(critique_status))}">{html.escape(str(critique_status))}</span>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Recommended Next Actions</h2>
      <div class="callout">Resolve required decisions, review AI guidance as advisory input, then validate the generated contracts in the target Databricks workspace before deployment.</div>
    </section>

    {_table_section("Decisions Required Before Use", ["Path", "Question", "Reason"], decision_rows)}
    {_table_section("Project Warnings", ["Warning"], warning_rows)}

    <section class="section">
      <h2>AI Guidance</h2>
      {provider_html or '<p>No AI guidance was attached to this review.</p>'}
    </section>

    <section class="section">
      <h2>Consolidated Project Guide</h2>
      {consolidated_html or '<p>No consolidated guidance artifact was attached to this report.</p>'}
    </section>

    {_table_section("Deterministic Validation", ["Status", "Check", "Summary"], validation_rows)}
    {_table_section("Validation Decisions", ["Decision", "Occurrences", "Affected scope"], validation_decision_rows)}
    {_table_section("Critique Findings", ["Severity", "Code", "Message"], critique_rows)}
    {_table_section("Critique Decisions", ["Decision", "Occurrences", "Affected scope"], critique_decision_rows)}
    {_table_section("Generated Artifacts", ["Path", "Kind", "Description"], artifact_rows)}
    {_table_section("Context Evidence", ["Path", "Format", "Bytes", "Sampled records"], context_rows)}

    {traceability_html}
  </main>
</body>
</html>
"""


def _intent_generation_markdown(
    *,
    project: Any,
    request: Any,
    schema_source: dict[str, Any],
    intent: Any,
    project_state: Any,
    gap_plan: Any,
    transformation_plan: Any,
    context_snapshot: Any,
    generation_signature: Any,
    policy_result: Any,
    audit_trail: Any,
    provider_proposal_audit: Any,
    transformation_enrichment: EnrichmentResult | None,
    pre_generation_enrichment: EnrichmentResult | None,
    enrichment: EnrichmentResult | None,
    title: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        "## Executive Summary",
        "",
        f"- Project: `{project.name}`",
        f"- Target: `{project.target}`",
        f"- Generated artifacts: `{len(project.artifacts)}`",
        f"- Policy action: `{policy_result.action}`",
        f"- Signature: `{generation_signature.signature_hash}`",
        f"- Context: `{context_snapshot.snapshot_hash}`",
        "",
        "## User Intent",
        "",
        str(request.prompt),
        "",
        "## Interpreted Plan",
        "",
        f"- Requested layers: `{', '.join(intent.requested_layers)}`",
        f"- Source: `{intent.source or 'REVIEW_REQUIRED'}`",
        f"- Target table: `{intent.target_table or 'not specified'}`",
        f"- Final columns: `{', '.join(intent.final_columns) if intent.final_columns else 'not specified'}`",
        f"- Completion goal: `{intent.completion_goal}`",
        f"- Schema source: `{schema_source.get('kind')}`",
        "",
        "## Generated Artifacts",
        "",
        *[f"- `{artifact.path}` ({artifact.kind}) - {artifact.description or 'generated artifact'}" for artifact in project.artifacts],
        "",
        "## Required Decisions",
        "",
    ]
    if project.report.decisions_required:
        for decision in project.report.decisions_required:
            lines.append(f"- `{decision.path or 'review'}` {decision.question} - {decision.reason}")
    else:
        lines.append("- No blocking decisions were produced by deterministic generation.")
    lines.extend(["", "## Audit Trail", "", f"- Events: `{len(audit_trail.events)}`", f"- Last hash: `{audit_trail.last_hash or 'none'}`"])
    if transformation_enrichment is not None or pre_generation_enrichment is not None or enrichment is not None:
        lines.extend(["", "## AI Guidance", ""])
        for name, item in (
            ("Transformation refinement", transformation_enrichment),
            ("Pre-generation review", pre_generation_enrichment),
            ("Post-generation review", enrichment),
        ):
            if item is not None:
                lines.extend(_enrichment_lines(name, item))
    return "\n".join(lines).rstrip() + "\n"


def _consolidated_artifact_lines(artifact: Any) -> list[str]:
    title = str(getattr(artifact, "path", "review content")).replace("\\", "/")
    description = getattr(artifact, "description", None)
    content = str(getattr(artifact, "content", "")).strip()
    lines = ["", f"### {title}", ""]
    if description:
        lines.extend([str(description), ""])
    if content:
        lines.extend(_demote_markdown_headings(content).splitlines())
    return lines


def _guided_traceability_blocks(*, project: Any, spec: Any, context: Any) -> list[tuple[str, Any]]:
    blocks: list[tuple[str, Any]] = []
    for name, owner in (("Project", project), ("Specification", spec), ("Context", context)):
        traceability = getattr(owner, "traceability", None) if owner is not None else None
        if traceability is not None:
            blocks.append((name, traceability))
    return blocks


def _guided_traceability_rows(*, project: Any, spec: Any, context: Any) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for name, traceability in _guided_traceability_blocks(project=project, spec=spec, context=context):
        evidence = list(getattr(traceability, "evidence", []) or [])
        assumptions = list(getattr(traceability, "assumptions", []) or [])
        decisions = list(getattr(traceability, "decisions_required", []) or [])
        rows.append(
            [
                name,
                f"{getattr(traceability, 'confidence_level', 'unknown')} ({float(getattr(traceability, 'confidence', 0.0)):.2f})",
                str(bool(getattr(traceability, "review_required", False) or decisions)).lower(),
                len(evidence),
                len(assumptions),
                len(decisions),
            ]
        )
    return rows


def _guided_evidence_rows(*, project: Any, spec: Any, context: Any) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for name, traceability in _guided_traceability_blocks(project=project, spec=spec, context=context):
        for item in list(getattr(traceability, "evidence", []) or []):
            rows.append(
                [
                    name,
                    getattr(item, "source", "unknown"),
                    getattr(item, "path", None) or "",
                    getattr(item, "reason", ""),
                    "" if getattr(item, "confidence", None) is None else f"{float(getattr(item, 'confidence')):.2f}",
                ]
            )
    return rows


def _guided_governance_payload(guided_result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name in (
        "context_snapshot",
        "generation_signature",
        "policy_result",
        "audit_trail",
        "provider_proposal_audit",
    ):
        value = getattr(guided_result, name, None)
        if value is not None:
            payload[name] = value
    return payload


def _guided_compact_traceability_markdown(governance: dict[str, Any]) -> list[str]:
    signature = governance.get("generation_signature")
    context_snapshot = governance.get("context_snapshot")
    audit_trail = governance.get("audit_trail")

    return [
        f"- Signature: `{getattr(signature, 'signature_hash', 'not recorded')}`",
        f"- Context: `{getattr(context_snapshot, 'snapshot_hash', 'not recorded')}`",
        "- Existing layers: `none detected`",
        f"- Audit events: `{len(getattr(audit_trail, 'events', []) or [])}`",
        f"- Last audit hash: `{getattr(audit_trail, 'last_hash', '') or 'none'}`",
    ]


def _guided_compact_traceability_html(governance: dict[str, Any]) -> str:
    if not governance:
        return ""
    signature = governance.get("generation_signature")
    context_snapshot = governance.get("context_snapshot")
    audit_trail = governance.get("audit_trail")
    return (
        '<section class="section">'
        "<h2>Traceability</h2>"
        '<div class="kv">'
        f"<strong>Signature</strong><span><code>{html.escape(str(getattr(signature, 'signature_hash', 'not recorded')))}</code></span>"
        f"<strong>Context</strong><span><code>{html.escape(str(getattr(context_snapshot, 'snapshot_hash', 'not recorded')))}</code></span>"
        "<strong>Existing layers</strong><span>none detected</span>"
        f"<strong>Audit events</strong><span>{len(getattr(audit_trail, 'events', []) or [])}</span>"
        f"<strong>Last audit hash</strong><span><code>{html.escape(str(getattr(audit_trail, 'last_hash', '') or 'none'))}</code></span>"
        "</div>"
        "</section>"
    )


def _demote_markdown_headings(markdown: str) -> str:
    lines = []
    for line in markdown.splitlines():
        if line.startswith("### "):
            lines.append(f"##### {line[4:]}")
        elif line.startswith("## "):
            lines.append(f"#### {line[3:]}")
        elif line.startswith("# "):
            lines.append(f"#### {line[2:]}")
        else:
            lines.append(line)
    return "\n".join(lines)


def _consolidated_html(artifacts: list[Any]) -> str:
    sections = []
    for artifact in artifacts:
        path = str(getattr(artifact, "path", "review content")).replace("\\", "/")
        description = getattr(artifact, "description", None)
        content = str(getattr(artifact, "content", "")).strip()
        body = _markdown_to_html(_demote_markdown_headings(content)) if content else "<p>No content was generated.</p>"
        description_html = f"<p>{html.escape(str(description))}</p>" if description else ""
        sections.append(
            "<details class=\"guide-block\">"
            f"<summary>{html.escape(path)}</summary>"
            f"{description_html}"
            f"{body}"
            "</details>"
        )
    return "\n".join(sections)


def _status_class(value: Any) -> str:
    normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    return "".join(char for char in normalized if char.isalnum() or char == "_") or "unknown"


def _provider_section_any(title: str, enrichment: EnrichmentResult | dict[str, Any]) -> str:
    payload = enrichment.to_dict() if hasattr(enrichment, "to_dict") else dict(enrichment)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    display_title = _ai_guidance_title(title)
    parts = [
        '<div class="card provider-card">',
        f"<h2>{html.escape(display_title)}</h2>",
    ]
    if data.get("summary"):
        parts.append(f"<p>{html.escape(str(data['summary']))}</p>")
    for key, label in (
        ("recommendations", "Recommendations"),
        ("decisions_required", "Decisions required"),
        ("evidence", "Evidence"),
        ("assumptions", "Assumptions"),
    ):
        values = data.get(key)
        if isinstance(values, list) and values:
            items = "".join(f"<li>{html.escape(str(item))}</li>" for item in values)
            parts.append(f"<h3>{html.escape(label)}</h3><ul>{items}</ul>")
    if data.get("confidence") is not None:
        parts.append(f"<p><strong>Confidence:</strong> {html.escape(str(data['confidence']))}</p>")
    if data.get("review_required") is not None:
        parts.append(f"<p><strong>Review required:</strong> {html.escape(str(data['review_required']).lower())}</p>")
    if payload.get("warnings"):
        warnings = "".join(f"<li>{html.escape(str(item))}</li>" for item in payload["warnings"])
        parts.append(f"<h3>Warnings</h3><ul>{warnings}</ul>")
    parts.append("</div>")
    return "\n".join(parts)


def _operational_markdown(
    analysis: Any,
    *,
    enrichment: EnrichmentResult | dict[str, Any] | None,
    title: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        "## Executive Summary",
        "",
        f"- Status: `{analysis.status}`",
        f"- Risk: `{analysis.risk}`",
        f"- Summary: {analysis.summary}",
        "",
        "## Metrics",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in analysis.metrics.items())
    if analysis.findings:
        lines.extend(["", "## Findings", ""])
        for finding in analysis.findings:
            lines.extend(
                [
                    f"### {finding.title}",
                    "",
                    f"- Severity: `{finding.severity}`",
                    f"- Code: `{finding.code}`",
                    f"- Detail: {finding.detail}",
                    f"- Recommendation: {finding.recommendation}",
                    "",
                ]
            )
    if analysis.recommendations:
        lines.extend(["", "## Deterministic Recommendations", ""])
        lines.extend(f"- {item}" for item in analysis.recommendations)
    if enrichment is not None:
        lines.extend(["", "## AI Guidance", ""])
        lines.extend(_enrichment_lines("Operational guidance", enrichment))
    if analysis.follow_up_queries:
        lines.extend(["", "## Follow-up Queries", ""])
        lines.extend(f"- `{item}`" for item in analysis.follow_up_queries)
    return "\n".join(lines).rstrip() + "\n"


def _operational_html(
    *,
    title: str,
    analysis: Any,
    enrichment: EnrichmentResult | dict[str, Any] | None,
) -> str:
    metrics = dict(getattr(analysis, "metrics", {}) or {})
    findings = list(getattr(analysis, "findings", []) or [])
    recommendations = list(getattr(analysis, "recommendations", []) or [])
    follow_up_queries = list(getattr(analysis, "follow_up_queries", []) or [])
    traceability = getattr(analysis, "traceability", None)
    evidence = list(getattr(traceability, "evidence", []) or []) if traceability is not None else []

    status = getattr(analysis, "status", "UNKNOWN")
    risk = getattr(analysis, "risk", "unknown")
    summary = getattr(analysis, "summary", "No summary was produced.")
    status_counts = metrics.get("status_counts") if isinstance(metrics.get("status_counts"), dict) else {}
    failure_clusters = metrics.get("failure_clusters") if isinstance(metrics.get("failure_clusters"), dict) else {}
    error_categories = metrics.get("error_categories") if isinstance(metrics.get("error_categories"), dict) else {}
    metric_rows = [[key, _format_metric_value(value)] for key, value in metrics.items() if not isinstance(value, dict)]
    status_rows = [[key, value] for key, value in status_counts.items()]
    failure_rows = [[key, value] for key, value in failure_clusters.items()]
    error_rows = [[key, value] for key, value in error_categories.items()]
    finding_rows = [
        [
            finding.severity,
            finding.code,
            finding.title,
            finding.detail,
            finding.recommendation,
        ]
        for finding in findings
    ]
    recommendation_rows = [[item] for item in recommendations]
    follow_up_rows = [[item] for item in follow_up_queries]
    evidence_rows = [
        [
            item.source,
            item.path or "not provided",
            item.reason,
            item.confidence,
        ]
        for item in evidence
    ]
    provider_html = _provider_section_any("Operational guidance", enrichment) if enrichment is not None else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>{_rich_report_css()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">A structured operational review built from ContractForge control-table evidence, deterministic findings and optional AI guidance.</p>
      <div class="badge-row">
        <span class="badge">Status: <span class="status-{html.escape(_status_class(status))}">{html.escape(str(status))}</span></span>
        <span class="badge">Risk: <span class="risk-{html.escape(_status_class(risk))}">{html.escape(str(risk))}</span></span>
        <span class="badge">Findings: {len(findings)}</span>
        <span class="badge">Recommendations: {len(recommendations)}</span>
      </div>
    </section>

    <section class="grid">
      {_metric_card("Runs", _format_metric_value(metrics.get("runs_total", 0)), "Control-table runs included in this analysis.")}
      {_metric_card("Failures", _format_metric_value(metrics.get("runs_failed", 0)), "Runs classified as failed, error or failed-equivalent.")}
      {_metric_card("Success rate", _format_metric_value(metrics.get("run_success_rate")), "Successful runs divided by total runs.")}
      {_metric_card("Rows written", _format_metric_value(metrics.get("rows_written_total", 0)), "Rows written across analyzed runs.")}
    </section>

    <section class="section">
      <h2>Executive Summary</h2>
      <div class="callout">{html.escape(str(summary))}</div>
    </section>

    {_table_section("Operational Metrics", ["Metric", "Value"], metric_rows)}
    {_table_section("Run Status Counts", ["Status", "Count"], status_rows)}
    {_table_section("Failure Clusters", ["Cluster", "Count"], failure_rows)}
    {_table_section("Error Categories", ["Category", "Count"], error_rows)}
    {_table_section("Findings", ["Severity", "Code", "Title", "Detail", "Recommendation"], finding_rows)}
    {_table_section("Deterministic Recommendations", ["Recommendation"], recommendation_rows)}
    {_table_section("Follow-up Queries", ["Query"], follow_up_rows)}
    {_table_section("Traceability Evidence", ["Source", "Path", "Reason", "Confidence"], evidence_rows)}

    <section class="section">
      <h2>AI Guidance</h2>
      {provider_html or '<p>No AI guidance was attached to this operational analysis.</p>'}
    </section>

    <section class="section">
      <h2>Recommended Next Actions</h2>
      <div class="callout">Use deterministic findings as the operational baseline, then apply AI guidance only as advisory context for remediation planning.</div>
    </section>
  </main>
</body>
</html>
"""


def _format_metric_value(value: Any) -> str:
    if value is None:
        return "not available"
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    return str(value)


def _rich_report_css() -> str:
    return """
    :root {
      --bg: #f5f1e8;
      --ink: #162c3a;
      --muted: #5e6b73;
      --surface: rgba(255,255,255,.92);
      --line: #e4dacb;
      --navy: #173b57;
      --copper: #b7792f;
      --green: #2f765c;
      --red: #a84436;
      --blue-soft: #e8f0f4;
      --amber-soft: #fbf0dc;
      --green-soft: #e4f2ec;
      --red-soft: #f8e8e4;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at 10% 0%, rgba(183,121,47,.18), transparent 32rem),
        radial-gradient(circle at 92% 10%, rgba(23,59,87,.16), transparent 30rem),
        linear-gradient(135deg, #f9f6ef 0%, var(--bg) 48%, #edf3f5 100%);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.56;
    }
    main {
      width: min(1240px, calc(100vw - 36px));
      margin: 34px auto 72px;
    }
    .hero {
      background: linear-gradient(135deg, rgba(255,255,255,.95), rgba(248,244,236,.92));
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: 0 26px 80px rgba(22,44,58,.13);
      padding: 38px;
      overflow: hidden;
      position: relative;
    }
    .hero::after {
      content: "";
      position: absolute;
      right: -100px;
      top: -100px;
      width: 320px;
      height: 320px;
      background: radial-gradient(circle, rgba(183,121,47,.18), transparent 70%);
    }
    h1 {
      margin: 0;
      max-width: 900px;
      font-size: clamp(2.1rem, 5vw, 4.6rem);
      line-height: .98;
      letter-spacing: -.065em;
      color: var(--navy);
    }
    .subtitle {
      max-width: 850px;
      color: var(--muted);
      font-size: 1.06rem;
      margin: 16px 0 0;
    }
    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 24px;
    }
    .badge {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--navy);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: .88rem;
      font-weight: 700;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin: 22px 0;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 20px;
      box-shadow: 0 16px 44px rgba(22,44,58,.08);
    }
    .card h2 {
      margin: 0 0 12px;
      font-size: 1rem;
      color: var(--muted);
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .card h3 {
      margin: 18px 0 8px;
      color: var(--navy);
      font-size: .9rem;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .metric {
      font-size: 2rem;
      line-height: 1;
      font-weight: 850;
      letter-spacing: -.04em;
      color: var(--navy);
    }
    .section {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 24px;
      margin: 18px 0;
      padding: 24px;
      box-shadow: 0 16px 44px rgba(22,44,58,.07);
    }
    .section h2 {
      margin: 0 0 14px;
      color: var(--navy);
      font-size: 1.35rem;
      letter-spacing: -.025em;
    }
    .kv {
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 8px 16px;
      color: var(--muted);
    }
    .kv strong { color: var(--ink); }
    table {
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 14px;
      font-size: .92rem;
    }
    .table-wrap {
      width: 100%;
      overflow-x: auto;
      border-radius: 14px;
    }
    th, td {
      border-bottom: 1px solid #ebe3d8;
      padding: 11px 12px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--navy);
      background: #f4ede2;
      font-size: .78rem;
      text-transform: uppercase;
      letter-spacing: .06em;
    }
    tr:last-child td { border-bottom: 0; }
    code {
      background: #f1ede5;
      border: 1px solid #e1d8c9;
      border-radius: 7px;
      padding: .1rem .32rem;
      color: #102d42;
      font-size: .9em;
    }
    pre {
      overflow-x: auto;
      border-radius: 16px;
      border: 1px solid #d9e0e3;
      background: #12293b;
      color: #f7f4ee;
      padding: 18px;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.03);
    }
    pre code {
      background: transparent;
      border: 0;
      color: inherit;
      padding: 0;
      white-space: pre;
    }
    .status-approve, .status-ready, .status-supported, .status-success, .status-accepted, .accepted { color: var(--green); font-weight: 800; }
    .status-pass, .status-low, .risk-low { color: var(--green); font-weight: 800; }
    .status-warn, .status-ready_with_warnings, .status-supported_with_warnings, .status-medium, .risk-medium { color: var(--copper); font-weight: 800; }
    .status-review_required, .status-needs_decisions, .status-not_run, .status-unknown, .status-requires_review, .requires_review { color: var(--copper); font-weight: 800; }
    .status-block, .status-invalid, .status-unsafe, .status-failed, .status-rejected, .rejected { color: var(--red); font-weight: 800; }
    .status-fail, .status-high, .status-critical, .risk-high, .risk-critical { color: var(--red); font-weight: 800; }
    .callout {
      border-left: 5px solid var(--copper);
      background: var(--amber-soft);
      padding: 14px 16px;
      border-radius: 14px;
      color: #5c4630;
    }
    .two-col {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }
    .guide-block {
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #fffaf3;
      padding: 16px 18px;
      margin: 14px 0;
    }
    .guide-block summary {
      cursor: pointer;
      color: var(--navy);
      font-weight: 800;
    }
    .guide-block h3,
    .guide-block h4,
    .guide-block h5 {
      color: var(--navy);
      margin: 18px 0 8px;
    }
    .guide-block ul { padding-left: 1.25rem; }
    .provider-card { margin: 14px 0; }
    .finding-list {
      display: grid;
      gap: 14px;
    }
    .finding-card,
    .evidence-card {
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #fffaf3;
      padding: 16px;
    }
    .finding-head {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 10px;
    }
    .severity-pill {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 999px;
      padding: 5px 9px;
      font-size: .76rem;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .finding-card h3 {
      margin: 0 0 12px;
      color: var(--navy);
      font-size: 1.04rem;
    }
    .finding-path {
      display: grid;
      gap: 6px;
      margin: 10px 0 14px;
    }
    .finding-path code {
      display: block;
      max-width: 100%;
      overflow-x: auto;
      white-space: nowrap;
    }
    .finding-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 14px;
    }
    .finding-grid strong,
    .finding-path strong {
      color: var(--navy);
      font-size: .78rem;
      letter-spacing: .05em;
      text-transform: uppercase;
    }
    .finding-grid p {
      margin: 6px 0 0;
    }
    .evidence-card pre {
      margin: 12px 0 0;
      padding: 12px;
      background: #f1ede5;
      color: var(--ink);
      border-color: #e1d8c9;
      box-shadow: none;
    }
    @media (max-width: 900px) {
      .grid, .two-col { grid-template-columns: 1fr; }
      .finding-grid { grid-template-columns: 1fr; }
      .kv { grid-template-columns: 1fr; }
      .hero { padding: 26px; }
    }
    """


def _intent_generation_html(
    *,
    title: str,
    project: Any,
    request: Any,
    schema_source: dict[str, Any],
    intent: Any,
    project_state: Any,
    gap_plan: Any,
    transformation_plan: Any,
    context_snapshot: Any,
    generation_signature: Any,
    policy_result: Any,
    audit_trail: Any,
    provider_proposal_audit: Any,
    transformation_enrichment: EnrichmentResult | None,
    pre_generation_enrichment: EnrichmentResult | None,
    enrichment: EnrichmentResult | None,
) -> str:
    proposals = provider_proposal_audit
    decision_rows = [
        [
            decision.path or "review",
            decision.question,
            decision.reason,
        ]
        for decision in project.report.decisions_required
    ]
    artifact_rows = [[artifact.path, artifact.kind, artifact.description or "generated artifact"] for artifact in project.artifacts]
    gap_rows = [[action.layer, action.action, action.reason] for action in gap_plan.actions]
    transform_rows = [
        [step.action, step.column, step.expression or "", step.reason or ""]
        for step in transformation_plan.steps
    ]
    provider_sections = [
        _provider_section("Transformation guidance", transformation_enrichment),
        _provider_section("Project guidance", pre_generation_enrichment),
        _provider_section("Review guidance", enrichment),
    ]
    provider_html = "\n".join(section for section in provider_sections if section)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>{_rich_report_css()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">A consolidated review of the interpreted request, deterministic plan, generated artifacts, policy gate and audit trail.</p>
      <div class="badge-row">
        <span class="badge">Project: {html.escape(str(project.name))}</span>
        <span class="badge">Target: {html.escape(str(project.target))}</span>
        <span class="badge">Policy: <span class="status-{html.escape(str(policy_result.action))}">{html.escape(str(policy_result.action))}</span></span>
        <span class="badge">Schema: {html.escape(str(schema_source.get("kind")))}</span>
      </div>
    </section>

    <section class="grid">
      {_metric_card("Artifacts", len(project.artifacts), "Implementation files generated for review.")}
      {_metric_card("Decisions", len(project.report.decisions_required), "Human decisions required before deployment.")}
      {_metric_card("Audit events", len(audit_trail.events), "Generation events recorded for traceability.")}
      {_metric_card("Review", getattr(proposals, "review_required_count", 0), "Suggested updates kept for human review.")}
    </section>

    <section class="section">
      <h2>User Intent</h2>
      <p>{html.escape(str(request.prompt))}</p>
    </section>

    <section class="two-col">
      <div class="section">
        <h2>Interpreted Plan</h2>
        <div class="kv">
          <strong>Layers</strong><span>{html.escape(", ".join(intent.requested_layers))}</span>
          <strong>Source</strong><span><code>{html.escape(str(intent.source or "REVIEW_REQUIRED"))}</code></span>
          <strong>Target table</strong><span><code>{html.escape(str(intent.target_table or "not specified"))}</code></span>
          <strong>Final columns</strong><span>{html.escape(", ".join(intent.final_columns) if intent.final_columns else "not specified")}</span>
          <strong>Completion goal</strong><span>{html.escape(str(intent.completion_goal))}</span>
        </div>
      </div>
      <div class="section">
        <h2>Traceability</h2>
        <div class="kv">
          <strong>Signature</strong><span><code>{html.escape(str(generation_signature.signature_hash))}</code></span>
          <strong>Context</strong><span><code>{html.escape(str(context_snapshot.snapshot_hash))}</code></span>
          <strong>Existing layers</strong><span>{html.escape(", ".join(project_state.layers) if project_state.layers else "none detected")}</span>
          <strong>Audit events</strong><span>{len(audit_trail.events)}</span>
          <strong>Last audit hash</strong><span><code>{html.escape(str(audit_trail.last_hash or "none"))}</code></span>
        </div>
      </div>
    </section>

    {_table_section("Gap Plan", ["Layer", "Action", "Reason"], gap_rows)}
    {_table_section("Transformation Plan", ["Action", "Column", "Expression", "Reason"], transform_rows)}
    {_table_section("Generated Artifacts", ["Path", "Kind", "Description"], artifact_rows)}
    {_table_section("Required Decisions", ["Path", "Question", "Reason"], decision_rows)}

    <section class="section">
      <h2>AI Guidance</h2>
      {provider_html or '<p>No AI guidance was attached to this generation.</p>'}
    </section>

    <section class="section">
      <h2>Recommended Next Actions</h2>
      <div class="callout">Review required decisions, inspect provider proposal audit outcomes, then validate the generated contracts in the target Databricks workspace before deployment.</div>
    </section>
  </main>
</body>
</html>
"""


def _validation_lines(validation: Any) -> list[str]:
    lines = [
        f"- Status: `{validation.status}`",
        f"- Ready: `{str(validation.ready).lower()}`",
        f"- Summary: {validation.summary}",
    ]
    if validation.checks:
        lines.extend(["", "### Checks", ""])
        for check in validation.checks:
            lines.append(f"- `{check.status}` `{check.kind}:{check.name}` - {check.summary}")
    if validation.decisions_required:
        lines.extend(["", "### Validation Decisions", ""])
        lines.extend(_compact_review_decision_markdown(validation.decisions_required))
    return lines


def _metric_card(title: str, value: Any, description: str) -> str:
    return (
        '<div class="card">'
        f"<h2>{html.escape(title)}</h2>"
        f'<div class="metric">{html.escape(str(value))}</div>'
        f"<p>{html.escape(description)}</p>"
        "</div>"
    )


def _table_section(title: str, headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return f'<section class="section"><h2>{html.escape(title)}</h2><p>No records for this section.</p></section>'
    head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            text = html.escape(str(value))
            class_attr = ""
            if index == 0:
                status_class = _status_class(value)
                if status_class in {
                    "accepted",
                    "rejected",
                    "requires_review",
                    "approve",
                    "block",
                    "review_required",
                    "ready",
                    "ready_with_warnings",
                    "needs_decisions",
                    "invalid",
                    "unsafe",
                    "success",
                    "failed",
                    "low",
                    "medium",
                    "high",
                    "critical",
                }:
                    class_attr = f' class="status-{html.escape(status_class)}"'
            cells.append(f"<td{class_attr}>{_code_if_path(text)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    body = "\n".join(body_rows)
    return (
        '<section class="section">'
        f"<h2>{html.escape(title)}</h2>"
        '<div class="table-wrap">'
        "<table>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        "</div>"
        "</section>"
    )


def _compact_review_decision_rows(items: list[Any]) -> list[list[Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        scope, decision = _split_review_decision(item)
        if not decision:
            continue
        group = grouped.setdefault(decision, {"count": 0, "project_count": 0, "scopes": []})
        group["count"] += 1
        if scope:
            scopes = group["scopes"]
            if scope not in scopes:
                scopes.append(scope)
        else:
            group["project_count"] += 1

    rows: list[list[Any]] = []
    for decision, group in grouped.items():
        rows.append([decision, group["count"], _review_decision_scope(group)])
    return rows


def _compact_review_decision_markdown(items: list[Any]) -> list[str]:
    return [
        f"- {decision} (occurrences: `{count}`, affected scope: `{scope}`)"
        for decision, count, scope in _compact_review_decision_rows(items)
    ]


def _split_review_decision(item: Any) -> tuple[str, str]:
    text = str(item).strip()
    if ": " not in text:
        return "", text
    prefix, decision = text.split(": ", 1)
    if _looks_like_review_scope(prefix):
        return prefix.strip(), decision.strip()
    return "", text


def _looks_like_review_scope(value: str) -> bool:
    prefix = value.strip()
    if not prefix or any(character.isspace() for character in prefix):
        return False
    return any(marker in prefix for marker in ("/", "\\", ".", "[", "]", "$"))


def _review_decision_scope(group: dict[str, Any]) -> str:
    scopes: list[str] = []
    if group.get("project_count"):
        scopes.append("project")
    scopes.extend(group.get("scopes") or [])
    if not scopes:
        return "project"
    visible = scopes[:4]
    remaining = len(scopes) - len(visible)
    suffix = f"; +{remaining} more" if remaining > 0 else ""
    return "; ".join(visible) + suffix


def _details_section(title: str, summary: str, body: str) -> str:
    return (
        '<section class="section">'
        f"<h2>{html.escape(title)}</h2>"
        '<details class="guide-block">'
        f"<summary>{html.escape(summary)}</summary>"
        f"{body}"
        "</details>"
        "</section>"
    )


def _code_if_path(escaped_text: str) -> str:
    normalized = escaped_text.replace("\\", "/")
    path_prefixes = (
        "contracts/",
        "connections/",
        "environments/",
        "examples/",
        ".tmp/",
        "project.yaml",
    )
    file_suffixes = (
        ".yaml",
        ".yml",
        ".json",
        ".html",
        ".md",
        ".py",
        ".sql",
        ".txt",
    )
    looks_like_path = normalized.startswith(path_prefixes) or normalized.endswith(file_suffixes) or "/" in normalized
    looks_like_structured_value = escaped_text.startswith("{") and escaped_text.endswith("}")
    looks_like_scope_summary = "; " in escaped_text
    if (looks_like_path and not looks_like_scope_summary) or looks_like_structured_value:
        return f"<code>{escaped_text}</code>"
    return escaped_text


def _provider_section(title: str, enrichment: EnrichmentResult | None) -> str:
    if enrichment is None:
        return ""
    payload = enrichment.to_dict()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    display_title = _ai_guidance_title(title)
    parts = [
        '<div class="card">',
        f"<h2>{html.escape(display_title)}</h2>",
    ]
    if data.get("summary"):
        parts.append(f"<p>{html.escape(str(data['summary']))}</p>")
    for key, label in (
        ("recommendations", "Recommendations"),
        ("decisions_required", "Decisions required"),
        ("evidence", "Evidence"),
        ("assumptions", "Assumptions"),
    ):
        values = data.get(key)
        if isinstance(values, list) and values:
            items = "".join(f"<li>{html.escape(str(item))}</li>" for item in values)
            parts.append(f"<h3>{html.escape(label)}</h3><ul>{items}</ul>")
    if payload.get("warnings"):
        warnings = "".join(f"<li>{html.escape(str(item))}</li>" for item in payload["warnings"])
        parts.append(f"<h3>Warnings</h3><ul>{warnings}</ul>")
    parts.append("</div>")
    return "\n".join(parts)


def _critique_lines(critique: Any) -> list[str]:
    lines = [
        f"- Status: `{critique.status}`",
        f"- Ready: `{str(critique.ready).lower()}`",
        f"- Confidence: `{critique.confidence:.2f}`",
        f"- Evidence coverage: `{critique.evidence_coverage:.2f}`",
        f"- Summary: {critique.summary}",
    ]
    if critique.findings:
        lines.extend(["", "### Critique Findings", ""])
        for finding in critique.findings:
            lines.append(f"- `{finding.severity}` `{finding.code}` - {finding.message}")
    if critique.decisions_required:
        lines.extend(["", "### Critique Decisions", ""])
        lines.extend(f"- {item}" for item in critique.decisions_required)
    return lines


def _enrichment_lines(name: str, enrichment: EnrichmentResult | dict[str, Any]) -> list[str]:
    payload = enrichment.to_dict() if hasattr(enrichment, "to_dict") else dict(enrichment)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    display_name = _ai_guidance_title(name)
    lines = [
        f"### {display_name}",
        "",
    ]
    if payload.get("warnings"):
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {item}" for item in payload["warnings"])
    if data:
        if data.get("summary"):
            lines.extend(["", f"Summary: {data['summary']}"])
        for section, title in (
            ("recommendations", "Recommendations"),
            ("decisions_required", "Decisions Required"),
            ("evidence", "Evidence"),
            ("assumptions", "Assumptions"),
        ):
            values = data.get(section)
            if isinstance(values, list) and values:
                lines.extend(["", f"{title}:"])
                lines.extend(f"- {item}" for item in values)
        if data.get("confidence") is not None:
            lines.extend(["", f"Confidence: `{data['confidence']}`"])
        if data.get("review_required") is not None:
            lines.append(f"Review required: `{str(data['review_required']).lower()}`")
    return lines


def _ai_guidance_title(title: str) -> str:
    normalized = title.strip().lower().replace("_", " ").replace("-", " ")
    provider_names = {"openai", "azure openai", "deepseek", "databricks", "anthropic", "gemini", "bedrock"}
    if normalized in provider_names:
        return "AI Guidance"
    if "specification" in normalized:
        return "Specification Guidance"
    if "transformation" in normalized:
        return "Transformation Guidance"
    if "pre generation" in normalized or "project" in normalized:
        return "Project Guidance"
    if "post generation" in normalized or "review" in normalized:
        return "Review Guidance"
    return "AI Guidance"


def _html_page(title: str, markdown: str) -> str:
    body_markdown = markdown
    first_line = f"# {title}"
    if body_markdown.splitlines()[:1] == [first_line]:
        body_markdown = "\n".join(body_markdown.splitlines()[1:]).lstrip()
    body = _markdown_to_html(body_markdown)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>{_rich_report_css()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">A ContractForge AI report rendered with the same visual system used by generation reviews.</p>
    </section>
    <section class="section">
{body}
    </section>
  </main>
</body>
</html>
"""


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    in_list = False
    in_code = False
    code_language = ""
    code_lines: list[str] = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            output.append("</ul>")
            in_list = False

    def close_code() -> None:
        nonlocal in_code, code_language, code_lines
        if in_code:
            class_attr = f' class="language-{html.escape(code_language)}"' if code_language else ""
            code = html.escape("\n".join(code_lines))
            output.append(f"<pre><code{class_attr}>{code}</code></pre>")
            in_code = False
            code_language = ""
            code_lines = []

    for line in lines:
        if line.startswith("```"):
            if in_code:
                close_code()
            else:
                close_list()
                in_code = True
                code_language = line[3:].strip()
                code_lines = []
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            close_list()
            continue
        if line.startswith("# "):
            close_list()
            output.append(f"<h1>{_inline(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            close_list()
            output.append(f"<h2>{_inline(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            close_list()
            output.append(f"<h3>{_inline(line[4:].strip())}</h3>")
        elif line.startswith("#### "):
            close_list()
            output.append(f"<h4>{_inline(line[5:].strip())}</h4>")
        elif line.startswith("##### "):
            close_list()
            output.append(f"<h5>{_inline(line[6:].strip())}</h5>")
        elif line.startswith("- "):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{_inline(line[2:].strip())}</li>")
        else:
            close_list()
            output.append(f"<p>{_inline(line.strip())}</p>")
    close_code()
    close_list()
    return "\n".join(f"    {line}" for line in output)


def _inline(value: str) -> str:
    escaped = html.escape(value)
    parts = escaped.split("`")
    if len(parts) == 1:
        return escaped
    rendered = []
    for index, part in enumerate(parts):
        rendered.append(f"<code>{part}</code>" if index % 2 else part)
    return "".join(rendered)


def _target_name(intent: Any) -> str:
    if intent is None:
        return "REVIEW_REQUIRED"
    values = [getattr(intent, "target_catalog", None), getattr(intent, "target_schema", None), getattr(intent, "target_table", None)]
    if all(values):
        return ".".join(str(value) for value in values)
    return "REVIEW_REQUIRED"


def _suffix(value: str | None) -> str:
    return f" - {value}" if value else ""
