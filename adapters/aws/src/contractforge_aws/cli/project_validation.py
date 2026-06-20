"""Validation rules for the AWS project deployment CLI."""

from __future__ import annotations

import argparse
from collections.abc import Callable


_Rule = tuple[Callable[[argparse.Namespace], bool], str]

_DEPLOY_PROJECT_RULES: tuple[_Rule, ...] = (
    (
        lambda args: not (args.dry_run and (args.run or args.wait)),
        "--dry-run cannot be combined with --run or --wait",
    ),
    (
        lambda args: not (args.dry_run and (args.run_orchestration or args.wait_orchestration)),
        "--dry-run cannot be combined with --run-orchestration or --wait-orchestration",
    ),
    (
        lambda args: not ((args.run or args.wait) and (args.run_orchestration or args.wait_orchestration)),
        "direct Glue --run/--wait cannot be combined with --run-orchestration/--wait-orchestration",
    ),
    (
        lambda args: not ((args.run_orchestration or args.wait_orchestration) and not args.deploy_orchestration),
        "--run-orchestration and --wait-orchestration require --deploy-orchestration in this CLI path",
    ),
    (
        lambda args: not (args.audit_evidence and (args.dry_run or not args.athena_output_location)),
        "--audit-evidence requires --athena-output-location and cannot be combined with --dry-run",
    ),
    (
        lambda args: not (args.audit_evidence and not (args.wait or args.wait_orchestration)),
        "--audit-evidence requires --wait or --wait-orchestration so audit runs after terminal states",
    ),
    (
        lambda args: not (
            args.record_cost_evidence
            and (args.dry_run or not (args.wait or args.wait_orchestration) or not args.athena_output_location)
        ),
        "--record-cost-evidence requires --wait or --wait-orchestration and --athena-output-location and cannot be combined with --dry-run",
    ),
)


def validate_deploy_project_args(args: argparse.Namespace) -> None:
    for valid, message in _DEPLOY_PROJECT_RULES:
        if not valid(args):
            raise ValueError(message)
