"""CLI handlers for ContractForge AI project generation commands."""

from __future__ import annotations

import json
import sys

from contractforge_ai.agentic import IntentGenerationRequest, generate_from_intent
from contractforge_ai.cli_io import load_mapping_file, load_text_file
from contractforge_ai.cli_output import (
    _html_artifact,
    _print_text_enrichment,
    _print_text_guided_project,
    _print_text_intent_generation,
    _print_text_project_plan,
    _print_text_project_planner,
)
from contractforge_ai.cli_payload import with_enrichment
from contractforge_ai.enrichment import enrich_project_plan
from contractforge_ai.generators.project import generate_project_for_target
from contractforge_ai.planning import ProjectPlannerRequest, plan_project_from_intent
from contractforge_ai.projects import write_project_plan
from contractforge_ai.projects.guided import GuidedProjectRequest, generate_guided_project
from contractforge_ai.providers import ProviderConfig, create_provider
from contractforge_ai.reports import render_markdown_report
from contractforge_ai.reports_translation import translate_report


def _handle_generate_project_command(args) -> int:
    naming = load_mapping_file(args.naming_file, purpose="Naming overrides") if args.naming_file else None
    plan = generate_project_for_target(
        args.target,
        args.schema,
        project_name=args.project_name,
        connector=args.connector,
        source_path=args.source_path,
        target_catalog=args.target_catalog,
        target_schema=args.target_schema,
        target_table=args.target_table,
        layer=args.layer,
        mode=args.mode,
        owner=args.owner,
        naming=naming,
        schedule_cron=args.schedule_cron,
        schedule_timezone=args.schedule_timezone,
        schedule_enabled=args.schedule_enabled,
    )
    if args.output_dir:
        results = write_project_plan(plan, args.output_dir, force=args.force, dry_run=args.dry_run)
        print(json.dumps({"artifacts": [item.to_dict() for item in results]}, indent=2, ensure_ascii=False))
    elif args.format == "json":
        print(json.dumps(plan.to_dict(include_content=True), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(plan.to_markdown())
    else:
        _print_text_project_plan(plan)
    return 0


def _handle_plan_project_command(args) -> int:
    intent = args.intent if args.intent is not None else load_text_file(args.intent_file)
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=intent,
            schema_path=args.schema_path,
            default_catalog=args.default_catalog,
            default_schema=args.default_schema,
            default_layer=args.default_layer,
            preferred_target=args.preferred_target,
        )
    )
    enrichment = (
        enrich_project_plan(
            result.to_dict(),
            intent,
            provider=create_provider(ProviderConfig.from_env(args.provider)),
        )
        if args.with_ai
        else None
    )
    if args.format == "json":
        print(json.dumps(with_enrichment(result.to_dict(), enrichment), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(result.to_markdown())
        if enrichment is not None:
            _print_text_enrichment(enrichment)
    else:
        _print_text_project_planner(result)
        if enrichment is not None:
            _print_text_enrichment(enrichment)
    return 0


def _handle_guided_project_command(args) -> int:
    request = _guided_project_request_from_args(args)
    result = generate_guided_project(request)
    if args.output_dir:
        if result.project is None:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            return 2
        results = write_project_plan(result.project, args.output_dir, force=args.force, dry_run=args.dry_run)
        print(
            json.dumps(
                {
                    "guided_project": result.to_dict(include_content=args.dry_run),
                    "artifacts": [item.to_dict() for item in results],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    elif args.format == "json":
        print(json.dumps(result.to_dict(include_content=True), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        report = render_markdown_report(result.to_markdown(), title="ContractForge AI Validation Report")
        print(translate_report(report, language=request.language, provider=request.provider).markdown)
    elif args.format == "html":
        report = render_markdown_report(result.to_markdown(), title="ContractForge AI Validation Report")
        print(translate_report(report, language=request.language, provider=request.provider).html)
    else:
        _print_text_guided_project(result)
    return 0


def _handle_generate_command(args) -> int:
    prompt = args.prompt if args.prompt is not None else load_text_file(args.prompt_file)
    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=prompt,
            schema_path=args.schema_path,
            schema_paths=tuple(args.schema_paths or ()),
            sample_table=args.sample_table,
            project_root=args.project_root,
            output_target=args.target,
            default_catalog=args.default_catalog,
            language=args.language,
            provider=create_provider(ProviderConfig.from_env(args.provider)) if args.with_ai else None,
        )
    )
    if args.output_dir:
        if result.project is None:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            return 2
        write_results = write_project_plan(result.project, args.output_dir, force=args.force, dry_run=args.dry_run)
        print(
            json.dumps(
                {
                    "generation": result.to_dict(include_content=args.dry_run),
                    "artifacts": [item.to_dict() for item in write_results],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    elif args.format == "json":
        print(json.dumps(result.to_dict(include_content=True), indent=2, ensure_ascii=False))
    elif args.format == "html":
        artifact = _html_artifact(result.project)
        print(
            artifact.content
            if artifact
            else render_markdown_report(
                "# ContractForge AI Generation\n\nNo project was generated.",
                title="ContractForge AI Generation",
            ).html
        )
    else:
        _print_text_intent_generation(result)
    return 0


PROJECT_GENERATION_COMMAND_HANDLERS = {
    "generate-project": _handle_generate_project_command,
    "plan-project": _handle_plan_project_command,
    "guided-project": _handle_guided_project_command,
    "generate": _handle_generate_command,
}


def _guided_project_request_from_args(args) -> GuidedProjectRequest:
    payload = load_mapping_file(args.requirements, purpose="Guided project requirements") if args.requirements else {}
    intent = _arg_or_payload(args.intent, payload, "intent")
    if intent is None and args.intent_file is not None:
        intent = load_text_file(args.intent_file)
    schema_path = _arg_or_payload(args.schema_path, payload, "schema_path")
    context_dir = _arg_or_payload(getattr(args, "context_dir", None), payload, "context_dir")
    if not intent:
        print("guided-project requires an intent in --intent, --intent-file or --requirements.", file=sys.stderr)
        raise SystemExit(2)
    if not schema_path and not context_dir:
        print("guided-project requires schema_path or context_dir in CLI flags or --requirements.", file=sys.stderr)
        raise SystemExit(2)
    return GuidedProjectRequest(
        intent=str(intent),
        schema_path=str(schema_path) if schema_path else None,
        context_dir=str(context_dir) if context_dir else None,
        runtime=_arg_or_payload(getattr(args, "runtime", None), payload, "runtime"),
        default_catalog=_arg_or_payload(args.default_catalog, payload, "default_catalog"),
        default_schema=_arg_or_payload(args.default_schema, payload, "default_schema"),
        default_layer=_arg_or_payload(args.default_layer, payload, "default_layer"),
        preferred_target=_arg_or_payload(args.target, payload, "preferred_target"),
        allow_review_required=bool(_arg_or_payload(args.allow_review_required, payload, "allow_review_required")),
        language=str(_arg_or_payload(getattr(args, "language", None), payload, "language") or "en"),
        naming=(
            load_mapping_file(args.naming_file, purpose="Naming overrides")
            if getattr(args, "naming_file", None)
            else payload.get("naming")
        ),
        provider=create_provider(ProviderConfig.from_env(args.provider)) if getattr(args, "with_ai", False) else None,
    )


def _arg_or_payload(value, payload: dict, key: str):
    if value not in (None, False):
        return value
    return payload.get(key)
