"""AWS deployment pipeline CLI commands."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from contractforge_aws.cli.support import (
    contract_bundle_artifacts,
    load_contract_input,
    load_environment_input,
)
from contractforge_aws.runtime import deploy_aws_contract_to_glue


def add_deploy_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    deploy = subparsers.add_parser(
        "deploy",
        help="Plan, render, publish artifacts and create or update the AWS Glue job.",
    )
    deploy.add_argument("contract", type=Path)
    deploy.add_argument("--environment", type=Path)
    deploy.add_argument("--bucket")
    deploy.add_argument("--prefix", default="")


def handle_deploy_command(args: argparse.Namespace) -> int | None:
    handler = _DEPLOY_COMMANDS.get(args.command)
    return None if handler is None else handler(args)


def _handle_deploy(args: argparse.Namespace) -> int:
    contract, bundle_environment = load_contract_input(args.contract)
    environment = load_environment_input(args.environment, bundle_environment)
    deployment = deploy_aws_contract_to_glue(
        contract,
        bucket=args.bucket,
        prefix=args.prefix,
        environment=environment,
        extra_artifacts=contract_bundle_artifacts(args.contract, environment=environment),
    )
    payload = asdict(deployment)
    payload["artifacts"] = [asdict(artifact) for artifact in deployment.artifacts]
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


_DEPLOY_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "deploy": _handle_deploy,
}
