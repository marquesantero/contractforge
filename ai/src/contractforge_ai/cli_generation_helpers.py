"""CLI handlers for deterministic generation helper commands."""

from __future__ import annotations

import json

import yaml

from contractforge_ai.cli_output import (
    _print_text_contract_draft,
    _print_text_metadata_suggestions,
    _print_text_project_plan,
    _print_text_shape_suggestions,
)
from contractforge_ai.generators.contract import generate_contract_draft
from contractforge_ai.generators.metadata import suggest_metadata
from contractforge_ai.generators.shape import suggest_shape
from contractforge_ai.projects import load_project_plan, write_project_plan


def _handle_suggest_metadata_command(args) -> int:
    result = suggest_metadata(args.schema)
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "yaml":
        print(yaml.safe_dump({"annotations": result.annotations, "quality_rules": result.quality_rules}, sort_keys=False))
    else:
        _print_text_metadata_suggestions(result)
    return 0


def _handle_suggest_shape_command(args) -> int:
    result = suggest_shape(args.sample, source_column=args.source_column)
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "yaml":
        print(yaml.safe_dump({"shape": result.shape}, sort_keys=False))
    else:
        _print_text_shape_suggestions(result)
    return 0


def _handle_generate_contract_command(args) -> int:
    result = generate_contract_draft(
        args.schema,
        connector=args.connector,
        source_path=args.source_path,
        target_catalog=args.target_catalog,
        target_schema=args.target_schema,
        target_table=args.target_table,
        layer=args.layer,
        mode=args.mode,
        owner=args.owner,
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "yaml":
        print(yaml.safe_dump(result.contract, sort_keys=False))
    else:
        _print_text_contract_draft(result)
    return 0


def _handle_project_plan_command(args) -> int:
    plan = load_project_plan(args.input)
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


GENERATION_HELPER_COMMAND_HANDLERS = {
    "suggest-metadata": _handle_suggest_metadata_command,
    "suggest-shape": _handle_suggest_shape_command,
    "generate-contract": _handle_generate_contract_command,
    "project-plan": _handle_project_plan_command,
}
