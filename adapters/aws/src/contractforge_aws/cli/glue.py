"""AWS CLI commands for Glue job lifecycle helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from contractforge_aws.cli.project_cost import record_project_step_cost_evidence
from contractforge_aws.cli.support import (
    load_contract_input,
    load_environment_input,
    parse_key_values,
    print_payload,
    public_payload,
)
from contractforge_aws.runtime import (
    get_aws_glue_job_run_status,
    reconcile_aws_glue_job_run_evidence,
    register_aws_glue_job,
    render_aws_glue_job_run_evidence_sql,
    start_aws_glue_job_run,
)


def add_glue_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    register = subparsers.add_parser("register-glue-job", help="Create or update an AWS Glue job definition.")
    register.add_argument("--job-name", required=True)
    register.add_argument("--role-arn", required=True)
    register.add_argument("--script-s3-uri", required=True)
    register.add_argument("--glue-version", default="4.0")
    register.add_argument("--worker-type", default="G.1X")
    register.add_argument("--number-of-workers", type=int, default=2)
    register.add_argument("--timeout-minutes", type=int, default=60)
    register.add_argument("--max-retries", type=int, default=0)
    register.add_argument("--enable-job-bookmark", action="store_true")
    register.add_argument("--default-argument", action="append", default=[], help="Glue default argument as key=value.")

    start = subparsers.add_parser("start-glue-job", help="Start a registered AWS Glue job.")
    start.add_argument("--job-name", required=True)
    start.add_argument("--argument", action="append", default=[], help="Glue argument as key=value.")

    status = subparsers.add_parser("glue-job-status", help="Get AWS Glue job run status.")
    status.add_argument("--job-name", required=True)
    status.add_argument("--run-id", required=True)

    reconcile = subparsers.add_parser("reconcile-glue-run", help="Map Glue job run metadata into evidence.")
    reconcile.add_argument("--job-name", required=True)
    reconcile.add_argument("--run-id", required=True)
    reconcile.add_argument("--target-table", required=True)
    reconcile.add_argument("--mode", required=True)

    record_cost = subparsers.add_parser(
        "record-glue-cost",
        help="Append Glue DPU-second cost evidence for an already completed Glue run.",
    )
    record_cost.add_argument("contract", type=Path)
    record_cost.add_argument("--environment", type=Path)
    record_cost.add_argument("--job-name", required=True)
    record_cost.add_argument("--run-id", required=True)
    record_cost.add_argument("--athena-output-location", required=True)
    record_cost.add_argument("--athena-workgroup")
    record_cost.add_argument("--poll-interval-seconds", type=float, default=2.0)
    record_cost.add_argument("--max-wait-seconds", type=float, default=300.0)

    sql = subparsers.add_parser("render-glue-run-sql", help="Render Iceberg INSERT SQL for Glue run evidence.")
    sql.add_argument("--job-name", required=True)
    sql.add_argument("--run-id", required=True)
    sql.add_argument("--target-table", required=True)
    sql.add_argument("--mode", required=True)
    sql.add_argument("--database", default="contractforge_ops")


def handle_glue_command(args: argparse.Namespace) -> int | None:
    handler = _GLUE_COMMANDS.get(args.command)
    return None if handler is None else handler(args)


def _handle_register_glue_job(args: argparse.Namespace) -> int:
    registered = register_aws_glue_job(
        job_name=args.job_name,
        role_arn=args.role_arn,
        script_s3_uri=args.script_s3_uri,
        glue_version=args.glue_version,
        worker_type=args.worker_type,
        number_of_workers=args.number_of_workers,
        timeout_minutes=args.timeout_minutes,
        max_retries=args.max_retries,
        enable_job_bookmark=args.enable_job_bookmark,
        default_arguments=parse_key_values(args.default_argument, flag="--default-argument"),
    )
    print_payload(public_payload(registered))
    return 0


def _handle_start_glue_job(args: argparse.Namespace) -> int:
    run = start_aws_glue_job_run(
        job_name=args.job_name,
        arguments=parse_key_values(args.argument, flag="--argument"),
    )
    print_payload(public_payload(run))
    return 0


def _handle_glue_job_status(args: argparse.Namespace) -> int:
    print_payload(public_payload(get_aws_glue_job_run_status(job_name=args.job_name, run_id=args.run_id)))
    return 0


def _handle_reconcile_glue_run(args: argparse.Namespace) -> int:
    evidence = reconcile_aws_glue_job_run_evidence(
        job_name=args.job_name,
        run_id=args.run_id,
        target_table=args.target_table,
        mode=args.mode,
    )
    print(json.dumps(_evidence_payload(evidence), indent=2, sort_keys=True, default=str))
    return 0


def _handle_render_glue_run_sql(args: argparse.Namespace) -> int:
    print(
        render_aws_glue_job_run_evidence_sql(
            job_name=args.job_name,
            run_id=args.run_id,
            target_table=args.target_table,
            mode=args.mode,
            database=args.database,
        )
    )
    return 0


def _handle_record_glue_cost(args: argparse.Namespace) -> int:
    contract, bundle_environment = load_contract_input(args.contract)
    environment = load_environment_input(args.environment, bundle_environment)
    payload = record_project_step_cost_evidence(
        environment,
        contract,
        job_name=args.job_name,
        run_id=args.run_id,
        athena_output_location=args.athena_output_location,
        athena_workgroup=args.athena_workgroup,
        poll_interval_seconds=args.poll_interval_seconds,
        max_wait_seconds=args.max_wait_seconds,
    )
    print_payload(payload)
    return 0


def _evidence_payload(evidence) -> dict[str, object]:
    return {
        "run": evidence.run.__dict__,
        "cost": None if evidence.cost is None else evidence.cost.__dict__,
        "operation_metrics": evidence.operation_metrics,
    }


_GLUE_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "register-glue-job": _handle_register_glue_job,
    "start-glue-job": _handle_start_glue_job,
    "glue-job-status": _handle_glue_job_status,
    "reconcile-glue-run": _handle_reconcile_glue_run,
    "record-glue-cost": _handle_record_glue_cost,
    "render-glue-run-sql": _handle_render_glue_run_sql,
}
