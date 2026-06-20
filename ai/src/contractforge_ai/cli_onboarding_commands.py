"""CLI handlers for ContractForge AI onboarding commands."""

from __future__ import annotations

import json

from contractforge_ai.cli_io import load_json_file
from contractforge_ai.cli_output import (
    _print_text_environment_report,
    _print_text_init_result,
    _print_text_profile,
    _print_text_profiles,
)
from contractforge_ai.onboarding import (
    AgentInstructionRequest,
    OnboardingInitRequest,
    build_onboarding_plan,
    discover_environment,
    generate_agent_instruction_plan,
    get_integration_profile,
    list_integration_profiles,
)
from contractforge_ai.projects import write_project_plan


def _handle_profiles_command(args) -> int:
    profiles = list_integration_profiles()
    if args.format == "json":
        print(json.dumps({"profiles": [profile.to_dict() for profile in profiles]}, indent=2, ensure_ascii=False))
    else:
        _print_text_profiles(profiles)
    return 0


def _handle_profile_command(args) -> int:
    profile = get_integration_profile(args.name)
    config = load_json_file(args.config) if args.config else {}
    report = profile.validate_config(config)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "profile": profile.to_dict(),
                    "validation": report.to_dict(),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        _print_text_profile(profile, report)
    return 0


def _handle_environment_report_command(args) -> int:
    report = discover_environment()
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        _print_text_environment_report(report)
    return 0


def _handle_init_command(args) -> int:
    plan = build_onboarding_plan(
        OnboardingInitRequest(
            profile=args.profile,
            provider_mode=args.mode,
            provider=args.provider,
            model=args.model,
            catalog=args.catalog,
            ctrl_schema=args.ctrl_schema,
            workspace_profile=args.workspace_profile,
            instruction_path=args.instruction_path,
            tool_boundary=args.tool_boundary,
        )
    )
    results = write_project_plan(plan, args.output_dir, force=args.force, dry_run=args.dry_run)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "plan": plan.to_dict(include_content=args.dry_run),
                    "artifacts": [item.to_dict() for item in results],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    elif args.format == "markdown":
        print(plan.to_markdown())
    else:
        _print_text_init_result(plan, results, dry_run=args.dry_run)
    return 0


def _handle_agent_instructions_command(args) -> int:
    instruction_request_kwargs = {
        "target": args.target,
        "project_name": args.project_name,
        "contract_root": args.contract_root,
        "output_prefix": args.output_prefix,
        "allow_production_mutation": args.allow_production_mutation,
    }
    if args.validation_commands:
        instruction_request_kwargs["validation_commands"] = args.validation_commands
    plan = generate_agent_instruction_plan(
        AgentInstructionRequest(**instruction_request_kwargs)
    )
    results = write_project_plan(plan, args.output_dir, force=args.force, dry_run=args.dry_run)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "plan": plan.to_dict(include_content=args.dry_run),
                    "artifacts": [item.to_dict() for item in results],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    elif args.format == "markdown":
        print(plan.to_markdown())
    else:
        _print_text_init_result(plan, results, dry_run=args.dry_run)
    return 0


ONBOARDING_COMMAND_HANDLERS = {
    "profiles": _handle_profiles_command,
    "profile": _handle_profile_command,
    "environment-report": _handle_environment_report_command,
    "init": _handle_init_command,
    "agent-instructions": _handle_agent_instructions_command,
}
