"""CLI handlers for validation, review, and provider routing commands."""

from __future__ import annotations

import json

from contractforge_ai.cli_io import (
    context_results_from_file,
    load_json_file,
    load_json_text,
    validation_report_from_file,
)
from contractforge_ai.cli_output import (
    _print_text_critique,
    _print_text_deterministic_validation,
    _print_text_enrichment_quality,
    _print_text_project_structure,
    _print_text_provider_evaluation,
    _print_text_provider_routing,
    _print_text_structured_output_validation,
    _project_structure_to_markdown,
)
from contractforge_ai.context.loaders import load_contract
from contractforge_ai.evaluation import (
    evaluate_enrichment_quality,
    evaluate_provider,
    load_json_payload,
    validate_model_output,
)
from contractforge_ai.intelligence import critique_output
from contractforge_ai.parity import compare_platforms
from contractforge_ai.projects import load_project_plan
from contractforge_ai.providers import ProviderConfig, ProviderRoutingRequest, create_provider, recommend_providers
from contractforge_ai.reports import render_markdown_report, render_project_structure_review
from contractforge_ai.reviewers.architecture import review_governed_architecture
from contractforge_ai.validation import (
    validate_contract_artifact,
    validate_model_artifact,
    validate_project_plan_artifact,
    validate_project_structure,
)


def _handle_validate_output_command(args, parser) -> int:
    del parser
    raw_output = load_json_text(args.input)
    fallback = load_json_file(args.fallback) if args.fallback else None
    result = validate_model_output(raw_output, prompt=args.prompt, deterministic_fallback=fallback)
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        _print_text_structured_output_validation(result)
    return 1 if result.status == "FAIL" else 0


def _handle_validate_artifact_command(args, parser) -> int:
    if args.contract:
        result = validate_contract_artifact(
            load_contract(args.contract),
            use_contractforge=not args.skip_contractforge,
            adapters=tuple(args.adapter),
        )
    elif args.project_plan:
        result = validate_project_plan_artifact(
            load_project_plan(args.project_plan),
            use_contractforge=not args.skip_contractforge,
            adapters=tuple(args.adapter),
        )
    elif args.project_root:
        result = validate_project_structure(args.project_root, adapters=tuple(args.adapter))
    else:
        if not args.prompt:
            parser.error("validate-artifact with --model-output requires --prompt")
        result = validate_model_artifact(
            load_json_text(args.model_output),
            prompt_name=args.prompt,
            deterministic_fallback=load_json_file(args.fallback) if args.fallback else None,
        )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(_project_structure_to_markdown(result) if args.project_root else result.to_markdown())
    elif args.format == "html":
        markdown = _project_structure_to_markdown(result) if args.project_root else result.to_markdown()
        print(render_markdown_report(markdown, title="ContractForge AI Critique Report").html)
    else:
        if args.project_root:
            _print_text_project_structure(result)
        else:
            _print_text_deterministic_validation(result)
    return 0 if result.ready else 1


def _handle_validate_project_structure_command(args, parser) -> int:
    del parser
    result = validate_project_structure(args.root, adapters=tuple(args.adapter))
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(_project_structure_to_markdown(result))
    elif args.format == "html":
        print(render_project_structure_review(result).html)
    else:
        _print_text_project_structure(result)
    return 0 if result.ready else 1


def _handle_compare_platforms_command(args, parser) -> int:
    del parser
    result = compare_platforms(
        contract=args.contract,
        project_root=args.project_root,
        adapters=tuple(args.adapter),
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(result.to_markdown())
    elif args.format == "html":
        print(render_markdown_report(result.to_markdown(), title="ContractForge Platform Parity Report").html)
    else:
        print(f"Platform parity: {result.status}")
        print(f"Ready: {str(result.ready).lower()}")
        print(f"Summary: {result.summary}")
        for contract in result.contracts:
            print()
            print(f"Contract: {contract.name}")
            print(f"- Source: {contract.source_type or 'unknown'}")
            print(f"- Target: {contract.target or 'unknown'}")
            print(f"- Mode: {contract.write_mode or 'unknown'}")
            for outcome in contract.adapter_outcomes:
                artifact_types = ", ".join(outcome.artifact_types) or "none"
                print(f"- {outcome.adapter}: {outcome.status} ({outcome.raw_status or 'UNKNOWN'}), artifacts: {artifact_types}")
    return 0 if result.ready else 1


def _handle_critique_output_command(args, parser) -> int:
    del parser
    validation = validation_report_from_file(args.validation) if args.validation else None
    result = critique_output(
        load_json_file(args.input),
        validation=validation,
        context_results=context_results_from_file(args.context) if args.context else None,
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(result.to_markdown())
    elif args.format == "html":
        print(render_markdown_report(result.to_markdown(), title="ContractForge AI Critique Report").html)
    else:
        _print_text_critique(result)
    return 0 if result.ready else 1


def _handle_review_architecture_command(args, parser) -> int:
    del parser
    result = review_governed_architecture(args.root)
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(result.to_markdown())
    elif args.format == "html":
        print(render_markdown_report(result.to_markdown(), title="Governed Architecture Review").html)
    else:
        print(f"Governed architecture score: {result.score:.0%}")
        for finding in result.findings:
            print(f"- {finding.concept}: {finding.status}")
    return 0


def _handle_eval_enrichment_command(args, parser) -> int:
    del parser
    result = evaluate_enrichment_quality(
        load_json_payload(args.deterministic),
        load_json_payload(args.enrichment),
        expected_kind=args.kind,
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(result.to_markdown())
    else:
        _print_text_enrichment_quality(result)
    return 1 if result.status == "FAIL" else 0


def _handle_eval_provider_command(args, parser) -> int:
    del parser
    result = evaluate_provider(
        create_provider(ProviderConfig.from_env(args.provider)),
        prompts=args.prompts,
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(result.to_markdown())
    else:
        _print_text_provider_evaluation(result)
    return 1 if result.status == "FAIL" else 0


def _handle_route_provider_command(args, parser) -> int:
    del parser
    result = recommend_providers(
        ProviderRoutingRequest(
            task=args.task,
            require_strict_schema=args.require_strict_schema,
            allow_planned=args.allow_planned,
            prefer_http_only=args.prefer_http_only,
            prefer_databricks_boundary=args.prefer_databricks_boundary,
            include_offline=args.include_offline,
            allowed_providers=tuple(args.allow_provider),
            excluded_providers=tuple(args.exclude_provider),
        )
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(result.to_markdown())
    else:
        _print_text_provider_routing(result)
    return 0


VALIDATION_COMMAND_HANDLERS = {
    "validate-output": _handle_validate_output_command,
    "validate-artifact": _handle_validate_artifact_command,
    "validate-project-structure": _handle_validate_project_structure_command,
    "compare-platforms": _handle_compare_platforms_command,
    "critique-output": _handle_critique_output_command,
    "review-architecture": _handle_review_architecture_command,
    "eval-enrichment": _handle_eval_enrichment_command,
    "eval-provider": _handle_eval_provider_command,
    "route-provider": _handle_route_provider_command,
}
