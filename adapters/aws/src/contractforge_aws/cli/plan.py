"""AWS CLI commands for planning, rendering and artifact publishing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from contractforge_aws.api import plan_aws_contract, render_aws_contract
from contractforge_aws.cli.support import contract_bundle_artifacts, load_contract_input, load_environment_input
from contractforge_aws.runtime import publish_aws_contract_artifacts_to_s3


def add_plan_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    plan = subparsers.add_parser("plan", help="Plan a contract against the AWS Glue Iceberg target.")
    plan.add_argument("contract", type=Path)
    plan.add_argument("--environment", type=Path)

    render = subparsers.add_parser("render", help="Render AWS planning review artifacts.")
    render.add_argument("contract", type=Path)
    render.add_argument("--environment", type=Path)

    publish = subparsers.add_parser("publish-s3", help="Render and upload AWS artifacts to S3.")
    publish.add_argument("contract", type=Path)
    publish.add_argument("--environment", type=Path)
    publish.add_argument("--bucket")
    publish.add_argument("--prefix", default="")


def handle_plan_command(args: argparse.Namespace) -> int | None:
    handler = _PLAN_COMMANDS.get(args.command)
    return None if handler is None else handler(args)


def _handle_plan(args: argparse.Namespace) -> int:
    contract, bundle_environment = load_contract_input(args.contract)
    environment = load_environment_input(args.environment, bundle_environment)
    result = plan_aws_contract(contract, environment=environment)
    print(json.dumps(_planning_payload(result), indent=2, sort_keys=True))
    return 0


def _handle_render(args: argparse.Namespace) -> int:
    contract, bundle_environment = load_contract_input(args.contract)
    environment = load_environment_input(args.environment, bundle_environment)
    artifacts = render_aws_contract(contract, environment=environment)
    print(json.dumps(artifacts.artifacts, indent=2, sort_keys=True))
    return 0


def _handle_publish_s3(args: argparse.Namespace) -> int:
    contract, bundle_environment = load_contract_input(args.contract)
    environment = load_environment_input(args.environment, bundle_environment)
    published = publish_aws_contract_artifacts_to_s3(
        contract,
        bucket=args.bucket,
        prefix=args.prefix,
        environment=environment,
        extra_artifacts=contract_bundle_artifacts(args.contract, environment=environment),
    )
    print(json.dumps([item.__dict__ for item in published], indent=2, sort_keys=True))
    return 0


def _planning_payload(result) -> dict[str, object]:
    return {
        "status": result.status,
        "blockers": [{"code": item.code, "message": item.message} for item in result.blockers],
        "warnings": [{"code": item.code, "message": item.message} for item in result.warnings],
        "plan": None
        if result.plan is None
        else {
            "platform": result.plan.platform,
            "evidence_required": result.plan.evidence_required,
            "steps": [{"name": step.name, "intent": step.intent} for step in result.plan.steps],
        },
    }


_PLAN_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "plan": _handle_plan,
    "render": _handle_render,
    "publish-s3": _handle_publish_s3,
}
