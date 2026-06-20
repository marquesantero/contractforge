"""Workflow command handlers for the ContractForge AI CLI."""

from __future__ import annotations

import json
import sys

from contractforge_ai.cli_io import load_json_file
from contractforge_ai.cli_output import (
    _print_text_control_table_analysis,
    _print_text_enrichment,
    _print_text_explanation,
    _print_text_review,
)
from contractforge_ai.cli_payload import with_enrichment
from contractforge_ai.context import collect_databricks_run_evidence
from contractforge_ai.context.loaders import load_contract
from contractforge_ai.enrichment import (
    enrich_control_table_analysis,
    enrich_failure_explanation,
    enrich_review_result,
)
from contractforge_ai.explainers.failure import explain_failure
from contractforge_ai.observability import analyze_control_tables
from contractforge_ai.observability.control_tables import load_control_table_evidence
from contractforge_ai.providers import ProviderConfig, create_provider
from contractforge_ai.reports import render_operational_analysis_review
from contractforge_ai.reports_translation import translate_report
from contractforge_ai.reviewers.contract import review_contract
from contractforge_ai.reviewers.output import review_to_markdown, should_fail_review


def _handle_review_command(args, parser) -> int:
    del parser
    result = review_contract(args.contract, bundle=args.bundle)
    enrichment = (
        enrich_review_result(
            result.to_dict(),
            load_contract(args.contract),
            provider=create_provider(ProviderConfig.from_env(args.provider)),
        )
        if args.with_ai
        else None
    )
    if args.format == "json":
        print(json.dumps(with_enrichment(result.to_dict(), enrichment), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(review_to_markdown(result))
    else:
        _print_text_review(result)
        if enrichment is not None:
            _print_text_enrichment(enrichment)
    return 1 if should_fail_review(result, fail_on=args.fail_on, fail_on_codes=args.fail_on_code) else 0


def _explain_input_requested(args) -> bool:
    return bool(args.input)


def _resolve_explain_input(args, parser):
    del parser
    return args.input


def _explain_run_id_requested(args) -> bool:
    return bool(args.run_id)


def _resolve_explain_databricks_run(args, parser):
    if not args.catalog:
        parser.error("explain-run with --run-id requires --catalog")
    return _databricks_run_evidence_collector()(
        run_id=args.run_id,
        catalog=args.catalog,
        ctrl_schema=args.ctrl_schema,
        limit=args.limit,
    )


EXPLAIN_RUN_EVIDENCE_RESOLVERS = (
    (_explain_input_requested, _resolve_explain_input),
    (_explain_run_id_requested, _resolve_explain_databricks_run),
)


def _databricks_run_evidence_collector():
    cli_module = sys.modules.get("contractforge_ai.cli")
    return getattr(cli_module, "collect_databricks_run_evidence", collect_databricks_run_evidence)


def _resolve_explain_run_evidence(args, parser):
    for requested, resolver in EXPLAIN_RUN_EVIDENCE_RESOLVERS:
        if requested(args):
            return resolver(args, parser)
    parser.error("explain-run requires either --input or --run-id")


def _handle_explain_run_command(args, parser) -> int:
    evidence = _resolve_explain_run_evidence(args, parser)
    result = explain_failure(evidence)
    evidence_payload = load_json_file(evidence) if isinstance(evidence, str) and args.input else evidence
    enrichment = (
        enrich_failure_explanation(
            result.to_dict(),
            evidence_payload if isinstance(evidence_payload, dict) else {},
            provider=create_provider(ProviderConfig.from_env(args.provider)),
        )
        if args.with_ai
        else None
    )
    if args.format == "json":
        print(json.dumps(with_enrichment(result.to_dict(), enrichment), indent=2, ensure_ascii=False))
    else:
        _print_text_explanation(result)
        if enrichment is not None:
            _print_text_enrichment(enrichment)
    return 0


def _handle_analyze_control_tables_command(args, parser) -> int:
    del parser
    evidence = load_control_table_evidence(args.input)
    result = analyze_control_tables(evidence)
    provider = create_provider(ProviderConfig.from_env(args.provider)) if args.with_ai else None
    enrichment = (
        enrich_control_table_analysis(
            result.to_dict(),
            evidence.to_dict(),
            provider=provider,
        )
        if args.with_ai
        else None
    )
    if args.format == "json":
        print(json.dumps(with_enrichment(result.to_dict(), enrichment), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        report = render_operational_analysis_review(result, enrichment=enrichment)
        print(translate_report(report, language=args.language, provider=provider).markdown)
    elif args.format == "html":
        report = render_operational_analysis_review(result, enrichment=enrichment)
        print(translate_report(report, language=args.language, provider=provider).html)
    else:
        _print_text_control_table_analysis(result)
        if enrichment is not None:
            _print_text_enrichment(enrichment)
    return 0


WORKFLOW_COMMAND_HANDLERS = {
    "review": _handle_review_command,
    "explain-run": _handle_explain_run_command,
    "analyze-control-tables": _handle_analyze_control_tables_command,
}
