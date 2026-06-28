"""Text output renderers for the ContractForge AI CLI."""

from __future__ import annotations

import json


def _html_artifact(project) -> object | None:
    if project is None:
        return None
    for artifact in project.artifacts:
        if artifact.path.endswith(".html"):
            return artifact
    return None


def _print_text_review(result) -> None:
    print(f"Contract: {result.contract_path}")
    print(f"Status: {result.status}")
    print(f"Risk: {result.risk}")
    print(f"Summary: {result.summary}")
    if not result.findings:
        return
    print()
    print("Findings:")
    for finding in result.findings:
        location = f" [{finding.path}]" if finding.path else ""
        print(f"- {finding.severity.upper()} {finding.code}{location}: {finding.title}")
        print(f"  Detail: {finding.detail}")
        print(f"  Recommendation: {finding.recommendation}")


def _print_text_explanation(result) -> None:
    print(f"Status: {result.status}")
    print(f"Primary category: {result.primary_category}")
    print(f"Risk: {result.risk}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Summary: {result.summary}")
    if result.evidence:
        print()
        print("Evidence:")
        for key, value in result.evidence.items():
            print(f"- {key}: {value}")
    if result.findings:
        print()
        print("Findings:")
        for finding in result.findings:
            print(f"- {finding.severity.upper()} {finding.code}: {finding.title}")
            print(f"  Detail: {finding.detail}")
    if result.recommended_actions:
        print()
        print("Recommended actions:")
        for action in result.recommended_actions:
            print(f"- {action}")


def _print_text_control_table_analysis(result) -> None:
    print(f"Status: {result.status}")
    print(f"Risk: {result.risk}")
    print(f"Summary: {result.summary}")
    print()
    print("Metrics:")
    for key, value in result.metrics.items():
        print(f"- {key}: {value}")
    if result.findings:
        print()
        print("Findings:")
        for finding in result.findings:
            location = f" [{finding.path}]" if finding.path else ""
            print(f"- {finding.severity.upper()} {finding.code}{location}: {finding.title}")
            print(f"  Detail: {finding.detail}")
            print(f"  Recommendation: {finding.recommendation}")
    if result.recommendations:
        print()
        print("Recommendations:")
        for item in result.recommendations:
            print(f"- {item}")


def _print_text_knowledge_results(results) -> None:
    print(f"Knowledge results: {len(results)}")
    for result in results:
        heading = f" > {result.heading}" if result.heading else ""
        print(f"- {result.source_path}:{result.start_line}-{result.end_line}{heading} score={result.score}")
        print(f"  Matched: {', '.join(result.matched_terms)}")
        print(f"  {result.excerpt}")


def _print_text_task_routing(result) -> None:
    print(f"Task: {result.task}")
    print(f"Prompt: {result.prompt_name or 'none'}")
    print(f"Provider task: {result.provider_task}")
    print(f"Confidence: {result.confidence:.2f}")
    if result.reasons:
        print()
        print("Reasons:")
        for reason in result.reasons:
            print(f"- {reason}")
    if result.warnings:
        print()
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    if result.context_results:
        print()
        print("Context:")
        for item in result.context_results:
            print(f"- {item.source_path}:{item.start_line}-{item.end_line} score={item.score}")


def _print_text_enrichment(enrichment) -> None:
    print()
    print("AI enrichment:")
    print(f"- Status: {enrichment.status}")
    print(f"- Provider: {enrichment.provider}")
    if enrichment.warnings:
        print("- Warnings:")
        for warning in enrichment.warnings:
            print(f"  - {warning}")
    if enrichment.data:
        print("- Summary:")
        print(f"  {enrichment.data.get('summary')}")


def _print_text_metadata_suggestions(result) -> None:
    print(f"Source: {result.source_path}")
    print(f"Suggestions: {len(result.suggestions)}")
    if result.warnings:
        print()
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    print()
    print("Suggested annotations:")
    print(json.dumps(result.annotations, indent=2, ensure_ascii=False))
    print()
    print("Suggested quality rules:")
    print(json.dumps(result.quality_rules, indent=2, ensure_ascii=False))
    if result.suggestions:
        print()
        print("Evidence:")
        for suggestion in result.suggestions:
            print(f"- {suggestion.kind} [{suggestion.target}] confidence={suggestion.confidence:.2f}")
            for evidence in suggestion.evidence:
                print(f"  - {evidence}")


def _print_text_shape_suggestions(result) -> None:
    print(f"Source: {result.source_path}")
    if result.warnings:
        print()
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    if result.decisions_required:
        print()
        print("Decisions required:")
        for decision in result.decisions_required:
            print(f"- {decision}")
    print()
    print("Suggested shape:")
    print(json.dumps(result.shape, indent=2, ensure_ascii=False))
    print()
    print("Discovered paths:")
    for item in result.discovered_paths:
        print(f"- {item['path']} ({item['kind']}, {item['type']})")


def _print_text_contract_draft(result) -> None:
    print(f"Source schema: {result.source_path}")
    print("Draft: true")
    if result.assumptions:
        print()
        print("Assumptions:")
        for assumption in result.assumptions:
            print(f"- {assumption}")
    if result.decisions_required:
        print()
        print("Decisions required:")
        for decision in result.decisions_required:
            print(f"- {decision}")
    if result.warnings:
        print()
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    print()
    print("Contract:")
    print(json.dumps(result.contract, indent=2, ensure_ascii=False))


def _print_text_project_plan(plan) -> None:
    print(f"Project: {plan.name}")
    print(f"Target: {plan.target}")
    print(f"Artifacts: {len(plan.artifacts)}")
    print()
    for artifact in plan.artifacts:
        description = f" - {artifact.description}" if artifact.description else ""
        print(f"- {artifact.path} ({artifact.kind}){description}")
    print()
    print("Report:")
    print(f"- {plan.report.summary}")
    if plan.report.decisions_required:
        print()
        print("Decisions required:")
        for decision in plan.report.decisions_required:
            print(f"- {decision.question}: {decision.reason}")


def _print_text_project_planner(result) -> None:
    print(f"Planning status: {result.status}")
    print(f"Connector: {result.intent.connector or 'REVIEW_REQUIRED'}")
    print(f"Source: {result.intent.source_path or 'REVIEW_REQUIRED'}")
    target = (
        f"{result.intent.target_catalog}.{result.intent.target_schema}.{result.intent.target_table}"
        if result.intent.target_catalog and result.intent.target_schema and result.intent.target_table
        else "REVIEW_REQUIRED"
    )
    print(f"Target: {target}")
    print(f"Layer: {result.intent.layer or 'REVIEW_REQUIRED'}")
    print(f"Mode: {result.intent.mode or 'REVIEW_REQUIRED'}")
    print()
    print("Recommendations:")
    for recommendation in result.recommendations:
        missing = f" (missing: {', '.join(recommendation.required_inputs)})" if recommendation.required_inputs else ""
        print(f"- {recommendation.target}: {recommendation.reason}{missing}")
        print(f"  Command: {recommendation.command}")
    if result.decisions_required:
        print()
        print("Decisions required:")
        for decision in result.decisions_required:
            print(f"- {decision.question}: {decision.reason}")


def _print_text_guided_project(result) -> None:
    print(f"Guided project status: {result.status}")
    print(f"Selected target: {result.selected_target or 'REVIEW_REQUIRED'}")
    print()
    _print_text_project_planner(result.planner)
    if result.project is not None:
        print()
        _print_text_project_plan(result.project)


def _print_text_intent_generation(result) -> None:
    print(f"Generation status: {result.status}")
    print(f"Layers: {', '.join(result.layers) if result.layers else 'REVIEW_REQUIRED'}")
    print(f"Schema source: {result.schema_source.get('kind', 'unknown')}")
    if result.project is not None:
        print()
        _print_text_project_plan(result.project)
        html = _html_artifact(result.project)
        if html is not None:
            print()
            print(f"Primary review artifact: {html.path}")


def _print_text_profiles(profiles) -> None:
    print("Integration profiles:")
    for profile in profiles:
        print(f"- {profile.name}: {profile.description}")
        if profile.recommended_commands:
            print("  Recommended commands:")
            for command in profile.recommended_commands:
                print(f"  - {command}")


def _print_text_profile(profile, report) -> None:
    print(f"Profile: {profile.name}")
    print(f"Description: {profile.description}")
    print(f"Validation: {report.status}")
    if profile.required_config:
        print()
        print("Required config:")
        for key in profile.required_config:
            print(f"- {key}")
    if profile.optional_config:
        print()
        print("Optional config:")
        for key in profile.optional_config:
            print(f"- {key}")
    if report.missing_required:
        print()
        print("Missing required config:")
        for key in report.missing_required:
            print(f"- {key}")
    if report.warnings:
        print()
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")
    if report.recommended_commands:
        print()
        print("Recommended commands:")
        for command in report.recommended_commands:
            print(f"- {command}")


def _print_text_environment_report(report) -> None:
    print("Environment report")
    print(f"Python: {report.python_version}")
    print(f"Platform: {report.platform}")
    print()
    print("Packages:")
    package_groups = report.to_dict().get("package_groups") or {"all": report.packages}
    for group_name, packages in package_groups.items():
        print(f"- {group_name}:")
        for name, available in packages.items():
            print(f"  - {name}: {'available' if available else 'missing'}")
    print()
    print("Commands:")
    for name, available in report.commands.items():
        print(f"- {name}: {'available' if available else 'missing'}")
    if report.provider_environment:
        print()
        print("Provider environment:")
        for key, value in report.provider_environment.items():
            state = "configured" if value.get("configured") else "missing"
            rendered = value.get("value")
            print(f"- {key}: {state} ({rendered})")
    if report.databricks:
        print()
        print("Databricks:")
        for key, value in report.databricks.items():
            print(f"- {key}: {value}")
    if report.warnings:
        print()
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")


def _print_text_init_result(plan, results, *, dry_run: bool) -> None:
    action = "Planned" if dry_run else "Wrote"
    print(f"{action} onboarding artifacts for {plan.name}")
    print()
    for result in results:
        reason = f" - {result.reason}" if result.reason else ""
        print(f"- {result.path}: {result.status}{reason}")
    if plan.report.warnings:
        print()
        print("Warnings:")
        for warning in plan.report.warnings:
            print(f"- {warning}")
    if plan.report.decisions_required:
        print()
        print("Decisions required:")
        for decision in plan.report.decisions_required:
            print(f"- {decision.question}: {decision.reason}")


def _print_text_prompt_templates(templates) -> None:
    print("Prompt templates:")
    for template in templates:
        print(f"- {template.name} ({template.version}): {template.purpose}")
        print(f"  Required variables: {', '.join(template.required_variables)}")


def _print_text_prompt_eval_results(results) -> None:
    passed = sum(1 for result in results if result.status == "PASS")
    failed = sum(1 for result in results if result.status == "FAIL")
    print(f"Prompt evaluation: {passed} passed, {failed} failed")
    for result in results:
        print(f"- {result.case} [{result.prompt}]: {result.status}")
        for finding in result.findings:
            print(f"  - {finding.severity.upper()} {finding.code}: {finding.message}")


def _print_text_enrichment_quality(result) -> None:
    print(f"Enrichment quality: {result.status}")
    print(f"Score: {result.score:.2f}")
    print(result.summary)
    if result.findings:
        print()
        print("Findings:")
        for finding in result.findings:
            print(f"- {finding.severity.upper()} {finding.code} [{finding.path}]: {finding.message}")


def _print_text_provider_evaluation(result) -> None:
    print(f"Provider evaluation: {result.status}")
    print(f"Provider: {result.provider}")
    print(result.summary)
    if result.capability:
        print()
        print("Capability:")
        print(f"- Structured output: {result.capability['structured_output_strategy']}")
        print(f"- Transport: {result.capability['transport_mode']}")
        print(f"- Databricks dependency: {result.capability['databricks_dependency_mode']}")
        print(f"- Needs local validation: {result.capability['needs_local_validation']}")
    print()
    print("Prompt results:")
    for prompt_result in result.prompt_results:
        latency = f"{prompt_result.latency_ms} ms" if prompt_result.latency_ms is not None else "n/a"
        print(f"- {prompt_result.prompt}: {prompt_result.status} ({latency})")
        print(f"  Structured output: {prompt_result.structured_output_status or 'n/a'}")
        print(f"  Enrichment quality: {prompt_result.enrichment_quality_status or 'n/a'}")
        for finding in prompt_result.findings:
            print(f"  - {finding.severity.upper()} {finding.code} [{finding.path}]: {finding.message}")


def _print_text_provider_routing(result) -> None:
    selected = result.selected.provider if result.selected else "none"
    print(f"Provider routing task: {result.request.task}")
    print(f"Selected: {selected}")
    print()
    print("Recommendations:")
    for recommendation in result.recommendations:
        marker = "selected" if recommendation.recommended else "candidate"
        if recommendation.blockers:
            marker = "blocked"
        print(f"- {recommendation.provider}: {marker}, score={recommendation.score}")
        print(f"  Structured output: {recommendation.structured_output_strategy}")
        print(f"  Databricks dependency: {recommendation.databricks_dependency_mode}")
        for blocker in recommendation.blockers:
            print(f"  Blocker: {blocker}")
        for warning in recommendation.warnings:
            print(f"  Warning: {warning}")
        for reason in recommendation.reasons:
            print(f"  Reason: {reason}")


def _print_text_structured_output_validation(result) -> None:
    print(f"Structured output validation: {result.status}")
    if result.findings:
        print()
        print("Findings:")
        for finding in result.findings:
            print(f"- {finding.severity.upper()} {finding.code} [{finding.path}]: {finding.message}")
    if result.deterministic_fallback is not None:
        print()
        print("Deterministic fallback is available.")


def _print_text_deterministic_validation(result) -> None:
    print(f"Deterministic validation: {result.status}")
    print(f"Ready: {str(result.ready).lower()}")
    print(f"Summary: {result.summary}")
    if result.checks:
        print()
        print("Checks:")
        for check in result.checks:
            print(f"- {check.status} {check.kind}:{check.name} - {check.summary}")
    if result.decisions_required:
        print()
        print("Decisions required:")
        for decision in result.decisions_required:
            print(f"- {decision}")


def _print_text_project_structure(result) -> None:
    print(f"Project structure: {result.status}")
    print(f"Ready: {str(result.ready).lower()}")
    print(f"Root: {result.root}")
    print(f"Summary: {result.summary}")
    if result.files:
        print()
        print("Files:")
        for item in result.files:
            label = item.kind
            if item.adapter:
                label = f"{label}:{item.adapter}"
            if item.name:
                label = f"{label}:{item.name}"
            print(f"- {label} {item.path}")
    if result.findings:
        print()
        print("Findings:")
        for finding in result.findings:
            path = f" [{finding.path}]" if finding.path else ""
            print(f"- {finding.severity.upper()} {finding.code}{path}: {finding.title}")
            print(f"  Detail: {finding.detail}")
            print(f"  Recommendation: {finding.recommendation}")


def _project_structure_to_markdown(result) -> str:
    lines = [
        "# ContractForge Project Structure Validation",
        "",
        f"- Status: `{result.status}`",
        f"- Ready: `{str(result.ready).lower()}`",
        f"- Root: `{result.root}`",
        f"- Summary: {result.summary}",
    ]
    if result.files:
        lines.extend(["", "## Files"])
        for item in result.files:
            label = item.kind
            suffix = []
            if item.adapter:
                suffix.append(f"adapter={item.adapter}")
            if item.name:
                suffix.append(f"name={item.name}")
            detail = f" ({', '.join(suffix)})" if suffix else ""
            lines.append(f"- `{item.path}` - `{label}`{detail}")
    if result.findings:
        lines.extend(["", "## Findings"])
        for finding in result.findings:
            path = f" `{finding.path}`" if finding.path else ""
            lines.extend(
                [
                    f"- `{finding.severity}` `{finding.code}`{path}: **{finding.title}**",
                    f"  - Detail: {finding.detail}",
                    f"  - Recommendation: {finding.recommendation}",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _print_text_critique(result) -> None:
    print(f"Critique: {result.status}")
    print(f"Ready: {str(result.ready).lower()}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Evidence coverage: {result.evidence_coverage:.2f}")
    print(f"Summary: {result.summary}")
    if result.findings:
        print()
        print("Findings:")
        for finding in result.findings:
            print(f"- {finding.severity.upper()} {finding.code}: {finding.message}")
    if result.decisions_required:
        print()
        print("Decisions required:")
        for decision in result.decisions_required:
            print(f"- {decision}")


