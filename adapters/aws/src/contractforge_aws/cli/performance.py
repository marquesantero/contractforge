"""AWS performance report CLI commands."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws.cli.project_support import project_evidence_database
from contractforge_aws.cli.support import load_contract_input, load_environment_input, print_payload
from contractforge_aws.performance import render_performance_benchmark_query
from contractforge_aws.runtime import AthenaSqlRunner


def add_performance_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    canonical = subparsers.add_parser(
        "performance-report",
        help="Render or run an AWS performance evidence report for a runtime-sensitive contract.",
    )
    _add_report_args(canonical)

    report = subparsers.add_parser(
        "benchmark-report",
        help="Render or run an AWS benchmark evidence report for a runtime-sensitive contract.",
    )
    _add_report_args(report)


def _add_report_args(report: argparse.ArgumentParser) -> None:
    report.add_argument("contract", type=Path)
    report.add_argument("--environment", type=Path)
    report.add_argument("--run", action="store_true", help="Execute the report through Athena.")
    report.add_argument("--athena-output-location")
    report.add_argument("--athena-workgroup")
    report.add_argument("--poll-interval-seconds", type=float, default=2.0)
    report.add_argument("--max-wait-seconds", type=float, default=300.0)


def handle_performance_command(args: argparse.Namespace) -> int | None:
    handler = _PERFORMANCE_COMMANDS.get(args.command)
    return None if handler is None else handler(args)


def _handle_benchmark_report(args: argparse.Namespace) -> int:
    _validate_benchmark_report_args(args)
    contract, bundle_environment = load_contract_input(args.contract)
    environment = load_environment_input(args.environment, bundle_environment)
    sql = render_performance_benchmark_query(
        semantic_contract_from_mapping(contract),
        evidence_database_name=project_evidence_database(environment),
    )
    if not args.run:
        print(sql, end="")
        return 0
    runner = AthenaSqlRunner(
        database=project_evidence_database(environment),
        output_location=args.athena_output_location,
        workgroup=args.athena_workgroup,
        wait=True,
        poll_interval_seconds=args.poll_interval_seconds,
        max_wait_seconds=args.max_wait_seconds,
    )
    print_payload({"status": "REPORTED", "rows": runner.query(sql)})
    return 0


def _validate_benchmark_report_args(args: argparse.Namespace) -> None:
    if args.run and not args.athena_output_location:
        raise ValueError("--run requires --athena-output-location")


_PERFORMANCE_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "benchmark-report": _handle_benchmark_report,
    "performance-report": _handle_benchmark_report,
}
