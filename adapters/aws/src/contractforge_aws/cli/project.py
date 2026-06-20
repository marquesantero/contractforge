"""AWS project-level deployment CLI commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractforge_aws.cli.project_orchestration import project_orchestration_payload
from contractforge_aws.cli.project_orchestration_cost import record_orchestration_cost_evidence
from contractforge_aws.cli.project_step import deploy_project_step
from contractforge_aws.cli.project_support import (
    dry_run_step_payload,
    project_environment_path,
    project_execution_steps,
    run_project_evidence_audit,
    step_contract_path,
)
from contractforge_aws.cli.project_validation import validate_deploy_project_args
from contractforge_aws.cli.support import load_contract_input, load_environment_input, load_mapping
from contractforge_aws.runtime import deploy_aws_contract_to_glue


def add_project_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    project = subparsers.add_parser(
        "deploy-project",
        help="Deploy all AWS contracts from a ContractForge project.yaml execution order.",
    )
    _add_project_arguments(project, include_run=True)
    run_project = subparsers.add_parser(
        "run-project",
        help="Deploy and run all AWS contracts from a ContractForge project.yaml execution order.",
    )
    _add_project_arguments(run_project, include_run=False)


def _add_project_arguments(project: argparse.ArgumentParser, *, include_run: bool) -> None:
    project.add_argument("project", type=Path)
    project.add_argument("--environment", type=Path, help="Override the AWS environment file declared in project.yaml.")
    project.add_argument("--environment-key", default="aws")
    project.add_argument("--bucket")
    project.add_argument("--prefix", default="")
    project.add_argument("--dry-run", action="store_true", help="Plan/render the project locally without AWS API calls.")
    project.add_argument("--summary-only", action="store_true", help="Omit verbose per-step artifact lists from output.")
    if include_run:
        project.add_argument("--run", action="store_true", help="Start each Glue job after deployment.")
    project.add_argument("--wait", action="store_true", help="Wait for each started Glue job to finish.")
    project.add_argument("--render-orchestration", action="store_true")
    project.add_argument("--deploy-orchestration", action="store_true")
    project.add_argument("--run-orchestration", action="store_true")
    project.add_argument("--wait-orchestration", action="store_true")
    project.add_argument("--audit-evidence", action="store_true")
    project.add_argument("--record-cost-evidence", action="store_true")
    project.add_argument("--athena-output-location")
    project.add_argument("--athena-workgroup")
    project.add_argument("--poll-interval-seconds", type=float, default=30.0)
    project.add_argument("--max-wait-seconds", type=float, default=3600.0)
    project.add_argument("--accept-expected-failures", action="store_true")


def handle_project_command(args: argparse.Namespace) -> int | None:
    return _handle_deploy_project(args) if args.command in {"deploy-project", "run-project"} else None


def _handle_deploy_project(args: argparse.Namespace) -> int:
    if not hasattr(args, "run"):
        args.run = bool(args.command == "run-project" and not args.dry_run)
    validate_deploy_project_args(args)
    project_path = args.project
    project_root = project_path.parent
    project = load_mapping(project_path, label="project")
    environment_path = args.environment or project_environment_path(project, project_root, args.environment_key)
    environment = load_environment_input(environment_path, None)
    steps = [
        _project_step(
            step,
            project_root=project_root,
            environment=environment,
            environment_key=args.environment_key,
            bucket=args.bucket,
            prefix=args.prefix,
            dry_run=bool(args.dry_run),
            run=bool(args.run or args.wait),
            wait=bool(args.wait),
            poll_interval_seconds=args.poll_interval_seconds,
            max_wait_seconds=args.max_wait_seconds,
            accept_expected_failures=bool(args.accept_expected_failures),
            record_cost_evidence=bool(args.record_cost_evidence),
            athena_output_location=args.athena_output_location,
            athena_workgroup=args.athena_workgroup,
            summary_only=bool(args.summary_only),
        )
        for step in project_execution_steps(project)
    ]
    payload: dict[str, object] = {
        "project": str(project_path),
        "environment": str(environment_path),
        "environment_key": args.environment_key,
        "dry_run": bool(args.dry_run),
        "steps": steps,
    }
    if args.render_orchestration or args.deploy_orchestration:
        payload["orchestration"] = project_orchestration_payload(
            project,
            steps,
            environment,
            deploy=bool(args.deploy_orchestration and not args.dry_run),
            run=bool(args.run_orchestration or args.wait_orchestration),
            wait=bool(args.wait_orchestration),
            poll_interval_seconds=args.poll_interval_seconds,
            max_wait_seconds=args.max_wait_seconds,
        )
        if args.record_cost_evidence:
            payload["orchestration"]["cost_evidence"] = record_orchestration_cost_evidence(
                project,
                project_root,
                environment_key=args.environment_key,
                environment=environment,
                orchestration=payload["orchestration"],
                athena_output_location=args.athena_output_location,
                athena_workgroup=args.athena_workgroup,
                poll_interval_seconds=args.poll_interval_seconds,
                max_wait_seconds=args.max_wait_seconds,
            )
    if args.audit_evidence:
        payload["evidence_audit"] = run_project_evidence_audit(
            environment,
            athena_output_location=args.athena_output_location,
            athena_workgroup=args.athena_workgroup,
            poll_interval_seconds=args.poll_interval_seconds,
            max_wait_seconds=args.max_wait_seconds,
        )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


def _project_step(
    step: dict,
    *,
    project_root: Path,
    environment: dict | None,
    environment_key: str,
    bucket: str | None,
    prefix: str,
    dry_run: bool,
    run: bool,
    wait: bool,
    poll_interval_seconds: float,
    max_wait_seconds: float,
    accept_expected_failures: bool,
    record_cost_evidence: bool,
    athena_output_location: str | None,
    athena_workgroup: str | None,
    summary_only: bool,
) -> dict[str, object]:
    contract_path = project_root / step_contract_path(step, environment_key)
    contract, bundle_environment = load_contract_input(contract_path)
    effective_environment = environment or bundle_environment
    if dry_run:
        return dry_run_step_payload(
            step,
            contract_path=contract_path,
            contract=contract,
            environment=effective_environment,
            summary_only=summary_only,
        )
    return deploy_project_step(
        step,
        contract_path=contract_path,
        contract=contract,
        environment=effective_environment,
        bucket=bucket,
        prefix=prefix,
        run=run,
        wait=wait,
        poll_interval_seconds=poll_interval_seconds,
        max_wait_seconds=max_wait_seconds,
        accept_expected_failures=accept_expected_failures,
        record_cost_evidence=record_cost_evidence,
        athena_output_location=athena_output_location,
        athena_workgroup=athena_workgroup,
        summary_only=summary_only,
        deployer=deploy_aws_contract_to_glue,
    )
