"""Minimal CLI entry point for the Fabric adapter package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from contractforge_fabric.api import plan_fabric_contract, render_fabric_contract
from contractforge_fabric.deployment import deploy_fabric_project
from contractforge_fabric.runtime import check_fabric_workspace_preflight
from contractforge_fabric.smoke import run_fabric_contract_smoke, run_fabric_project_smoke
from contractforge_fabric.stabilization import fabric_stabilization_report
from contractforge_fabric.sources import list_fabric_source_support


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-fabric")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Plan a contract against the Fabric Lakehouse target.")
    plan.add_argument("contract", type=Path)
    plan.add_argument("--environment", type=Path)

    render = subparsers.add_parser("render", help="Render Fabric planning review artifacts.")
    render.add_argument("contract", type=Path)
    render.add_argument("--environment", type=Path)

    preflight = subparsers.add_parser("preflight", help="Check Fabric workspace runtime prerequisites.")
    preflight.add_argument("--environment", type=Path, required=True)
    preflight.add_argument("--require-lakehouse", action="store_true")
    preflight.add_argument("--require-notebook", action="store_true")
    preflight.add_argument("--check-spark-settings", action="store_true")
    preflight.add_argument("--check-notebook-jobs", action="store_true")

    smoke = subparsers.add_parser("smoke", help="Deploy and optionally run a contract-generated Fabric notebook.")
    smoke.add_argument("contract", type=Path)
    smoke.add_argument("--environment", type=Path, required=True)
    smoke.add_argument("--no-wait", action="store_true")
    smoke.add_argument("--max-attempts", type=int, default=30)
    smoke.add_argument("--retry-after-seconds", type=int)

    smoke_project = subparsers.add_parser("run-project", help="Run Fabric smoke for every project execution step.")
    smoke_project.add_argument("project", type=Path)
    smoke_project.add_argument("--environment", type=Path)
    smoke_project.add_argument("--environment-key", default="fabric")
    smoke_project.add_argument("--no-wait", action="store_true")
    smoke_project.add_argument("--max-attempts", type=int, default=30)
    smoke_project.add_argument("--retry-after-seconds", type=int)
    smoke_project.add_argument("--continue-on-failure", action="store_true")
    smoke_project.add_argument("--start-at")

    deploy_project = subparsers.add_parser("deploy-project", help="Deploy Fabric project notebooks without running them.")
    deploy_project.add_argument("project", type=Path)
    deploy_project.add_argument("--environment", type=Path)
    deploy_project.add_argument("--environment-key", default="fabric")
    deploy_project.add_argument("--dry-run", action="store_true")
    deploy_project.add_argument("--update-existing", action="store_true")
    deploy_project.add_argument("--max-attempts", type=int, default=30)
    deploy_project.add_argument("--summary-only", action="store_true")

    stabilization = subparsers.add_parser(
        "stabilization-report",
        help="Print the Fabric adapter stabilization status for the notebook-first subset.",
    )
    stabilization.add_argument(
        "--strict-final",
        action="store_true",
        help="Return a non-zero exit code while Fabric is not stable-final.",
    )

    subparsers.add_parser("sources", help="Print Fabric source support metadata.")

    args = parser.parse_args(argv)
    if args.command == "plan":
        return _handle_plan(args.contract, args.environment)
    if args.command == "render":
        return _handle_render(args.contract, args.environment)
    if args.command == "preflight":
        return _handle_preflight(
            args.environment,
            args.require_lakehouse,
            args.require_notebook,
            args.check_spark_settings,
            args.check_notebook_jobs,
        )
    if args.command == "smoke":
        return _handle_smoke(
            args.contract,
            args.environment,
            wait=not args.no_wait,
            max_attempts=args.max_attempts,
            retry_after_seconds=args.retry_after_seconds,
        )
    if args.command == "run-project":
        return _handle_smoke_project(
            args.project,
            args.environment,
            environment_key=args.environment_key,
            wait=not args.no_wait,
            max_attempts=args.max_attempts,
            retry_after_seconds=args.retry_after_seconds,
            stop_on_failure=not args.continue_on_failure,
            start_at=args.start_at,
        )
    if args.command == "deploy-project":
        return _handle_deploy_project(
            args.project,
            args.environment,
            environment_key=args.environment_key,
            dry_run=args.dry_run,
            update_existing=args.update_existing,
            max_attempts=args.max_attempts,
            summary_only=args.summary_only,
        )
    if args.command == "sources":
        print(json.dumps(list(list_fabric_source_support()), indent=2, sort_keys=True))
        return 0
    if args.command == "stabilization-report":
        payload = fabric_stabilization_report()
        print(json.dumps(payload, indent=2, sort_keys=True))
        if args.strict_final and payload["stable_final"] is not True:
            return 1
        return 0
    return 2


def _handle_plan(contract_path: Path, environment_path: Path | None) -> int:
    result = plan_fabric_contract(_load_yaml(contract_path), environment=_load_optional_yaml(environment_path))
    print(json.dumps(_planning_payload(result), indent=2, sort_keys=True))
    return 0


def _handle_render(contract_path: Path, environment_path: Path | None) -> int:
    artifacts = render_fabric_contract(_load_yaml(contract_path), environment=_load_optional_yaml(environment_path))
    print(json.dumps(artifacts.artifacts, indent=2, sort_keys=True))
    return 0


def _handle_preflight(
    environment_path: Path,
    require_lakehouse: bool,
    require_notebook: bool,
    check_spark_settings: bool,
    check_notebook_jobs: bool,
) -> int:
    result = check_fabric_workspace_preflight(
        _load_yaml(environment_path),
        require_lakehouse=require_lakehouse,
        require_notebook=require_notebook,
        check_spark_settings=check_spark_settings,
        check_notebook_jobs=check_notebook_jobs,
    )
    print(json.dumps(_preflight_payload(result), indent=2, sort_keys=True))
    return 0 if result.ok else 1


def _handle_smoke(
    contract_path: Path,
    environment_path: Path,
    *,
    wait: bool,
    max_attempts: int,
    retry_after_seconds: int | None,
) -> int:
    result = run_fabric_contract_smoke(
        _load_yaml(contract_path),
        _load_yaml(environment_path),
        wait=wait,
        max_attempts=max_attempts,
        retry_after_seconds=retry_after_seconds,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    if result.ok:
        return 0
    return 2 if result.status == "BLOCKED" else 1


def _handle_smoke_project(
    project_path: Path,
    environment_path: Path | None,
    *,
    environment_key: str,
    wait: bool,
    max_attempts: int,
    retry_after_seconds: int | None,
    stop_on_failure: bool,
    start_at: str | None,
) -> int:
    result = run_fabric_project_smoke(
        project_path,
        environment=environment_path,
        environment_key=environment_key,
        wait=wait,
        max_attempts=max_attempts,
        retry_after_seconds=retry_after_seconds,
        stop_on_failure=stop_on_failure,
        start_at=start_at,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    if result.ok or result.status == "RUNNING":
        return 0
    return 2 if result.status == "BLOCKED" else 1


def _handle_deploy_project(
    project_path: Path,
    environment_path: Path | None,
    *,
    environment_key: str,
    dry_run: bool,
    update_existing: bool,
    max_attempts: int,
    summary_only: bool,
) -> int:
    result = deploy_fabric_project(
        project_path,
        environment=environment_path,
        environment_key=environment_key,
        dry_run=dry_run,
        update_existing=update_existing,
        max_attempts=max_attempts,
    )
    print(json.dumps(result.to_dict(summary_only=summary_only), indent=2, sort_keys=True))
    return 0 if result.ok else 2


def _load_optional_yaml(path: Path | None) -> dict[str, Any] | None:
    return None if path is None else _load_yaml(path)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML object in {path}")
    return payload


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


def _preflight_payload(result) -> dict[str, object]:
    return {
        "status": result.status,
        "ok": result.ok,
        "workspace": result.workspace,
        "items": result.items,
        "checks": [
            {
                "code": check.code,
                "status": check.status,
                "message": check.message,
                "details": check.details,
            }
            for check in result.checks
        ],
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
