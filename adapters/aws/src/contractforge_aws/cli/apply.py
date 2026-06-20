"""AWS CLI subcommands that apply rendered contract metadata."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from contractforge_aws.cli.support import load_mapping, print_payload, public_payload
from contractforge_aws.runtime import (
    AthenaSqlRunner,
    apply_aws_annotations_contract,
    apply_aws_lake_formation_contract,
    record_aws_operations_contract,
)


def add_apply_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    annotations = subparsers.add_parser("apply-annotations", help="Apply Glue Catalog annotations from a contract.")
    annotations.add_argument("contract", type=Path)
    annotations.add_argument("--catalog-id")
    annotations.add_argument("--no-skip-archive", action="store_true")

    lakeformation = subparsers.add_parser(
        "apply-lakeformation",
        help="Apply Lake Formation grants from a contract; data cell filters require explicit opt-in.",
    )
    lakeformation.add_argument("contract", type=Path)
    lakeformation.add_argument("--account-id")
    lakeformation.add_argument("--allow-data-cells-filters", action="store_true")

    operations = subparsers.add_parser("record-operations", help="Record operations metadata through Athena.")
    operations.add_argument("contract", type=Path)
    operations.add_argument("--database")
    operations.add_argument("--run-id", default="${run_id}")
    operations.add_argument("--athena-output-location", required=True)
    operations.add_argument("--athena-workgroup")
    operations.add_argument("--no-wait", action="store_true")
    operations.add_argument("--poll-interval-seconds", type=float, default=2.0)
    operations.add_argument("--max-wait-seconds", type=float, default=300.0)


def handle_apply_command(args: argparse.Namespace) -> int | None:
    handler = _APPLY_COMMANDS.get(args.command)
    return None if handler is None else handler(args)


def _handle_apply_annotations(args: argparse.Namespace) -> int:
    result = apply_aws_annotations_contract(
        load_mapping(args.contract, label="contract"),
        catalog_id=args.catalog_id,
        skip_archive=not args.no_skip_archive,
    )
    print_payload(public_payload(result))
    return 0


def _handle_apply_lakeformation(args: argparse.Namespace) -> int:
    result = apply_aws_lake_formation_contract(
        load_mapping(args.contract, label="contract"),
        account_id=args.account_id,
        allow_data_cells_filters=args.allow_data_cells_filters,
    )
    print_payload(public_payload(result))
    return 0


def _handle_record_operations(args: argparse.Namespace) -> int:
    runner = AthenaSqlRunner(
        database=args.database,
        output_location=args.athena_output_location,
        workgroup=args.athena_workgroup,
        wait=not args.no_wait,
        poll_interval_seconds=args.poll_interval_seconds,
        max_wait_seconds=args.max_wait_seconds,
    )
    result = record_aws_operations_contract(
        runner=runner,
        contract=load_mapping(args.contract, label="contract"),
        database=args.database,
        run_id=args.run_id,
    )
    print_payload(public_payload(result))
    return 0


_APPLY_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "apply-annotations": _handle_apply_annotations,
    "apply-lakeformation": _handle_apply_lakeformation,
    "record-operations": _handle_record_operations,
}
