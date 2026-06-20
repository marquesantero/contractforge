"""Project command handlers for deploy-project, run-project and cleanup-plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def add_project_parsers(subcommands: Any) -> None:
    deploy = subcommands.add_parser("deploy-project", help="Publish all Snowflake contracts from project.yaml.")
    deploy.add_argument("project", type=Path)
    deploy.add_argument("--environment", type=Path)
    deploy.add_argument("--environment-key", default="snowflake")
    deploy.add_argument("--stage")
    deploy.add_argument("--prefix")
    deploy.add_argument("--connect-options", type=Path)
    deploy.add_argument("--dry-run", action="store_true")
    deploy.add_argument("--summary-only", action="store_true")

    run_p = subcommands.add_parser("run-project", help="Execute root tasks for an already deployed Snowflake project.")
    run_p.add_argument("project", type=Path)
    run_p.add_argument("--environment", type=Path)
    run_p.add_argument("--environment-key", default="snowflake")
    run_p.add_argument("--connect-options", type=Path)
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--wait", action="store_true")
    run_p.add_argument("--poll-interval-seconds", type=float, default=10.0)
    run_p.add_argument("--max-wait-seconds", type=float, default=3600.0)
    run_p.add_argument("--summary-only", action="store_true")

    cleanup = subcommands.add_parser("cleanup-plan", help="Render a non-destructive Snowflake project cleanup plan.")
    cleanup.add_argument("project", type=Path)
    cleanup.add_argument("--environment", type=Path)
    cleanup.add_argument("--environment-key", default="snowflake")


def handle_deploy_project(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli._helpers import _load_optional_yaml
    from contractforge_snowflake.runtime import deploy_snowflake_project, project_deployment_json

    result = deploy_snowflake_project(
        args.project,
        environment=args.environment,
        environment_key=args.environment_key,
        stage=args.stage,
        prefix=args.prefix,
        dry_run=args.dry_run,
        summary_only=args.summary_only,
        connect_options=_load_optional_yaml(args.connect_options),
    )
    print(project_deployment_json(result, summary_only=args.summary_only))
    return 0


def handle_run_project(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _project_run_payload
    from contractforge_snowflake.runtime import run_snowflake_project

    result = run_snowflake_project(
        args.project,
        environment=args.environment,
        environment_key=args.environment_key,
        dry_run=args.dry_run,
        wait=args.wait,
        poll_interval_seconds=args.poll_interval_seconds,
        max_wait_seconds=args.max_wait_seconds,
        connect_options=_load_optional_yaml(args.connect_options),
    )
    print(json.dumps(_project_run_payload(result, summary_only=args.summary_only), indent=2, sort_keys=True, default=str))
    return 0


def handle_cleanup_plan(args: argparse.Namespace) -> int:
    from contractforge_snowflake.runtime import build_snowflake_project_cleanup_plan

    result = build_snowflake_project_cleanup_plan(
        args.project,
        environment=args.environment,
        environment_key=args.environment_key,
    )
    print(json.dumps(result.__dict__, indent=2, sort_keys=True, default=str))
    return 0
