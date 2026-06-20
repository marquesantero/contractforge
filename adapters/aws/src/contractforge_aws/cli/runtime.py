"""AWS runtime CLI subcommands kept outside the main CLI module."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from contractforge_aws.cli.support import load_payload, print_payload, public_payload
from contractforge_aws.runtime import (
    AthenaSqlRunner,
    audit_evidence_tables,
    ensure_aws_evidence_tables,
    register_aws_glue_job_definition_payload,
    wait_aws_glue_job_run,
)


def add_runtime_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    payload_parser = subparsers.add_parser(
        "register-glue-job-payload",
        help="Create or update an AWS Glue job from a rendered Glue job payload.",
    )
    payload_parser.add_argument("payload", type=Path)

    wait_parser = subparsers.add_parser("wait-glue-job", help="Wait for an AWS Glue job run to finish.")
    wait_parser.add_argument("--job-name", required=True)
    wait_parser.add_argument("--run-id", required=True)
    wait_parser.add_argument("--poll-interval-seconds", type=float, default=10.0)
    wait_parser.add_argument("--max-wait-seconds", type=float, default=3600.0)

    evidence_parser = subparsers.add_parser(
        "ensure-evidence-tables",
        help="Create ContractForge AWS Iceberg evidence tables through Athena.",
    )
    evidence_parser.add_argument("--database", default="contractforge_ops")
    evidence_parser.add_argument("--athena-output-location", required=True)
    evidence_parser.add_argument(
        "--warehouse-uri",
        required=True,
        help="S3 warehouse prefix for Athena-created Iceberg evidence tables.",
    )
    evidence_parser.add_argument("--athena-workgroup")
    evidence_parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    evidence_parser.add_argument("--max-wait-seconds", type=float, default=300.0)
    evidence_parser.add_argument("--skip-state", action="store_true")

    audit_parser = subparsers.add_parser(
        "audit-evidence",
        help="Run the standard ContractForge AWS evidence audit queries through Athena.",
    )
    audit_parser.add_argument("--database", required=True)
    audit_parser.add_argument("--athena-output-location", required=True)
    audit_parser.add_argument("--athena-workgroup")
    audit_parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    audit_parser.add_argument("--max-wait-seconds", type=float, default=300.0)


def handle_runtime_command(args: argparse.Namespace) -> int | None:
    handler = _RUNTIME_COMMANDS.get(args.command)
    return None if handler is None else handler(args)


def _handle_register_glue_job_payload(args: argparse.Namespace) -> int:
    registered = register_aws_glue_job_definition_payload(load_payload(args.payload))
    print_payload(public_payload(registered))
    return 0


def _handle_wait_glue_job(args: argparse.Namespace) -> int:
    status = wait_aws_glue_job_run(
        job_name=args.job_name,
        run_id=args.run_id,
        poll_interval_seconds=args.poll_interval_seconds,
        max_wait_seconds=args.max_wait_seconds,
    )
    print_payload(public_payload(status))
    return 0


def _handle_ensure_evidence_tables(args: argparse.Namespace) -> int:
    runner = AthenaSqlRunner(
        database=args.database,
        output_location=args.athena_output_location,
        workgroup=args.athena_workgroup,
        wait=True,
        poll_interval_seconds=args.poll_interval_seconds,
        max_wait_seconds=args.max_wait_seconds,
    )
    setup = ensure_aws_evidence_tables(
        runner=runner,
        database=args.database,
        include_state=not args.skip_state,
        dialect="athena",
        warehouse_uri=args.warehouse_uri,
    )
    print_payload(public_payload(setup))
    return 0


def _handle_audit_evidence(args: argparse.Namespace) -> int:
    runner = AthenaSqlRunner(
        database=args.database,
        output_location=args.athena_output_location,
        workgroup=args.athena_workgroup,
        wait=True,
        poll_interval_seconds=args.poll_interval_seconds,
        max_wait_seconds=args.max_wait_seconds,
    )
    audit = audit_evidence_tables(runner=runner, database=args.database)
    print_payload(public_payload(audit))
    return 0


_RUNTIME_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "register-glue-job-payload": _handle_register_glue_job_payload,
    "wait-glue-job": _handle_wait_glue_job,
    "ensure-evidence-tables": _handle_ensure_evidence_tables,
    "audit-evidence": _handle_audit_evidence,
}
