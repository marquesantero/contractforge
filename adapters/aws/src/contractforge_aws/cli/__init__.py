"""Minimal CLI entry point for the AWS adapter package."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Optional

from contractforge_aws.cli.apply import add_apply_subparsers, handle_apply_command
from contractforge_aws.cli.cost import add_cost_subparsers, handle_cost_command
from contractforge_aws.cli.deploy import add_deploy_subparsers, handle_deploy_command
from contractforge_aws.cli.glue import add_glue_subparsers, handle_glue_command
from contractforge_aws.cli.plan import add_plan_subparsers, handle_plan_command
from contractforge_aws.cli.performance import add_performance_subparsers, handle_performance_command
from contractforge_aws.cli.project_cleanup import add_cleanup_project_parser, handle_cleanup_project_command
from contractforge_aws.cli.project import add_project_subparsers, handle_project_command
from contractforge_aws.cli.runtime import add_runtime_subparsers, handle_runtime_command
from contractforge_aws.cli.smoke import add_smoke_subparsers, handle_smoke_command
from contractforge_aws.cli.stabilization import add_stabilization_subparsers, handle_stabilization_command
from contractforge_aws.sources import list_aws_source_support

_Handler = Callable[[argparse.Namespace], Optional[int]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-aws")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_plan_subparsers(subparsers)
    add_deploy_subparsers(subparsers)
    add_project_subparsers(subparsers)
    add_cleanup_project_parser(subparsers)
    add_glue_subparsers(subparsers)
    add_smoke_subparsers(subparsers)
    add_apply_subparsers(subparsers)
    add_runtime_subparsers(subparsers)
    add_performance_subparsers(subparsers)
    add_cost_subparsers(subparsers)
    subparsers.add_parser("sources", help="Print AWS source support metadata.")
    add_stabilization_subparsers(subparsers)

    args = parser.parse_args(argv)
    if args.command == "sources":
        print(json.dumps(list(list_aws_source_support()), indent=2, sort_keys=True))
        return 0
    for handler in _handlers():
        result = handler(args)
        if result is not None:
            return result
    return 2


def _handlers() -> tuple[_Handler, ...]:
    return (
        handle_plan_command,
        handle_deploy_command,
        handle_project_command,
        handle_cleanup_project_command,
        handle_glue_command,
        handle_smoke_command,
        handle_apply_command,
        handle_runtime_command,
        handle_performance_command,
        handle_cost_command,
        handle_stabilization_command,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
