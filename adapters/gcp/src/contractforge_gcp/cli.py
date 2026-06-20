"""CLI entry point for the ContractForge GCP adapter package."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import yaml

from contractforge_gcp.api import plan_gcp_contract, render_gcp_contract
from contractforge_gcp.cost import CostModel, build_operational_cost_report
from contractforge_gcp.dataplex import run_dataplex_data_quality, run_dataplex_lineage_aspects
from contractforge_gcp.deployment import deploy_gcp_project
from contractforge_gcp.deployment.workflows_runtime import run_gcp_workflows_orchestration
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.governance import run_bigquery_governance_reconciliation
from contractforge_gcp.smoke import (
    project_smoke_result_json,
    run_gcp_contract_smoke,
    run_gcp_project_smoke,
    smoke_result_json,
)
from contractforge_gcp.source_promotion import run_gcp_source_promotion
from contractforge_gcp.sources import list_gcp_source_support
from contractforge_gcp.stabilization import gcp_stabilization_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-gcp")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Plan a contract against the GCP BigQuery target.")
    plan.add_argument("contract", type=Path)
    plan.add_argument("--environment", type=Path)

    render = subparsers.add_parser("render", help="Render GCP BigQuery planning artifacts.")
    render.add_argument("contract", type=Path)
    render.add_argument("--environment", type=Path)
    render.add_argument("--output-dir", type=Path, help="Write rendered artifacts to this directory.")

    smoke = subparsers.add_parser("smoke", help="Dry-run or execute a single GCP BigQuery contract smoke.")
    smoke.add_argument("contract", type=Path)
    smoke.add_argument("--environment", type=Path)
    smoke.add_argument("--execute", action="store_true", help="Run BigQuery jobs. Default is dry-run only.")
    smoke.add_argument("--runtime", choices=("auto", "bq", "python"), default="auto")
    smoke.add_argument("--skip-evidence-ddl", action="store_true")
    smoke.add_argument("--skip-evidence-write", action="store_true")
    smoke.add_argument("--skip-quality", action="store_true")
    smoke.add_argument("--enforce-schema-policy", action="store_true")
    smoke.add_argument("--allow-review-required", action="store_true")
    smoke.add_argument("--report", type=Path, help="Write the smoke result JSON to this path.")

    dataplex_quality = subparsers.add_parser(
        "dataplex-quality",
        help="Render or execute native Dataplex DataScan quality for a contract.",
    )
    dataplex_quality.add_argument("contract", type=Path)
    dataplex_quality.add_argument("--environment", type=Path)
    dataplex_quality.add_argument("--execute", action="store_true", help="Create and run the generated DataScan.")
    dataplex_quality.add_argument("--wait", action="store_true", help="Poll the DataScan job until it reaches a terminal state.")
    dataplex_quality.add_argument("--readback", action="store_true", help="Read back the configured BigQuery export table.")
    dataplex_quality.add_argument("--cleanup", action="store_true", help="Delete the generated DataScan after execution.")
    dataplex_quality.add_argument("--timeout-seconds", type=int, default=300)
    dataplex_quality.add_argument("--poll-interval-seconds", type=int, default=10)
    dataplex_quality.add_argument("--report", type=Path, help="Write the Dataplex result JSON to this path.")

    dataplex_lineage = subparsers.add_parser(
        "dataplex-lineage-aspects",
        help="Render or execute native Dataplex lineage and aspect plans for a contract.",
    )
    dataplex_lineage.add_argument("contract", type=Path)
    dataplex_lineage.add_argument("--environment", type=Path)
    dataplex_lineage.add_argument("--execute", action="store_true", help="Publish lineage/aspects through native APIs.")
    dataplex_lineage.add_argument("--lineage-only", action="store_true", help="Execute only the native lineage plan.")
    dataplex_lineage.add_argument("--aspects-only", action="store_true", help="Execute only the native aspect plan.")
    dataplex_lineage.add_argument("--readback", action="store_true", help="Read back native lineage/aspect API responses.")
    dataplex_lineage.add_argument("--cleanup-aspect-type", action="store_true", help="Delete the generated AspectType after execution.")
    dataplex_lineage.add_argument("--run-id", help="Run id to use in native lineage publication.")
    dataplex_lineage.add_argument("--report", type=Path, help="Write the Dataplex lineage/aspect result JSON to this path.")

    deploy_project = subparsers.add_parser(
        "deploy-project",
        help="Render a dry-run GCP project deployment manifest and per-contract bundles.",
    )
    deploy_project.add_argument("project", type=Path)
    deploy_project.add_argument("--environment", type=Path)
    deploy_project.add_argument("--environment-key", default="gcp")
    deploy_project.add_argument("--dry-run", action="store_true", help="Accepted for CLI parity; GCP deploy-project is dry-run only.")
    deploy_project.add_argument("--output-dir", type=Path)
    deploy_project.add_argument("--summary-only", action="store_true")
    deploy_project.add_argument("--render-orchestration", action="store_true")
    deploy_project.add_argument("--deploy-orchestration", action="store_true")
    deploy_project.add_argument("--run-orchestration", action="store_true")
    deploy_project.add_argument("--wait-orchestration", action="store_true")
    deploy_project.add_argument("--readback-orchestration", action="store_true")
    deploy_project.add_argument("--reset-orchestration-data", action="store_true")
    deploy_project.add_argument("--cleanup-orchestration", action="store_true")
    deploy_project.add_argument("--cleanup-orchestration-data", action="store_true")
    deploy_project.add_argument("--readback-location")
    deploy_project.add_argument("--workflow-service-account")
    deploy_project.add_argument("--workflow-execution-id")

    run_project = subparsers.add_parser(
        "run-project",
        help="Dry-run or execute GCP project contracts sequentially through the BigQuery smoke runtime.",
    )
    run_project.add_argument("project", type=Path)
    run_project.add_argument("--environment", type=Path)
    run_project.add_argument("--environment-key", default="gcp")
    run_project.add_argument("--execute", action="store_true", help="Run BigQuery jobs. Default is dry-run only.")
    run_project.add_argument("--runtime", choices=("auto", "bq", "python"), default="auto")
    run_project.add_argument("--skip-evidence-ddl", action="store_true")
    run_project.add_argument("--skip-evidence-write", action="store_true")
    run_project.add_argument("--skip-quality", action="store_true")
    run_project.add_argument("--enforce-schema-policy", action="store_true")
    run_project.add_argument("--allow-review-required", action="store_true")
    run_project.add_argument("--continue-on-failure", action="store_true")
    run_project.add_argument("--start-at")
    run_project.add_argument("--report", type=Path, help="Write the project smoke result JSON to this path.")

    source_promotion = subparsers.add_parser(
        "source-promotion",
        help="Render or execute a GCP source-family promotion plan.",
    )
    source_promotion.add_argument("contract", type=Path)
    source_promotion.add_argument("--environment", type=Path)
    source_promotion.add_argument("--execute", action="store_true", help="Apply supported promotion commands.")
    source_promotion.add_argument("--readback", action="store_true", help="Read back provider metadata after apply.")
    source_promotion.add_argument("--report", type=Path, help="Write the promotion result JSON to this path.")

    governance_reconcile = subparsers.add_parser(
        "governance-reconcile",
        help="Read BigQuery governance state and compare it with contract intent.",
    )
    governance_reconcile.add_argument("contract", type=Path)
    governance_reconcile.add_argument("--environment", type=Path)
    governance_reconcile.add_argument("--execute", action="store_true", help="Run non-mutating BigQuery readback commands.")
    governance_reconcile.add_argument("--report", type=Path, help="Write the reconciliation result JSON to this path.")

    subparsers.add_parser("sources", help="Print GCP source support metadata.")

    stabilization = subparsers.add_parser("stabilization-report", help="Print GCP adapter stabilization status.")
    stabilization.add_argument("--strict-final", action="store_true")

    cost = subparsers.add_parser(
        "cost-report",
        help="Render a query-only BigQuery operational cost report from ContractForge run evidence.",
    )
    cost.add_argument("--environment", type=Path)
    cost.add_argument("--project-id")
    cost.add_argument("--dataset")
    cost.add_argument("--lookback-days", type=int, default=30)
    cost.add_argument("--group-by", action="append")
    cost.add_argument("--success-only", action="store_true")
    cost.add_argument("--bytes-processed-per-tib-rate", type=float)
    cost.add_argument("--slot-hour-rate", type=float)
    cost.add_argument("--currency", default="USD")
    cost.add_argument("--limit", type=int, default=100)

    args = parser.parse_args(argv)
    if args.command == "plan":
        result = plan_gcp_contract(_load_yaml(args.contract), environment=_load_optional_yaml(args.environment))
        print(json.dumps(_planning_payload(result), indent=2, sort_keys=True))
        return 0
    if args.command == "render":
        artifacts = render_gcp_contract(_load_yaml(args.contract), environment=_load_optional_yaml(args.environment))
        if args.output_dir:
            written = _write_artifacts(args.output_dir, artifacts.artifacts)
            print(json.dumps({"output_dir": str(args.output_dir), "artifacts": written}, indent=2, sort_keys=True))
            return 0
        print(json.dumps(artifacts.artifacts, indent=2, sort_keys=True))
        return 0
    if args.command == "smoke":
        result = run_gcp_contract_smoke(
            _load_yaml(args.contract),
            environment=_load_optional_yaml(args.environment),
            execute=args.execute,
            runtime=args.runtime,
            prepare_evidence=not args.skip_evidence_ddl,
            persist_evidence=not args.skip_evidence_write,
            run_quality=not args.skip_quality,
            enforce_schema_policy=args.enforce_schema_policy,
            allow_review_required=args.allow_review_required,
        )
        payload = smoke_result_json(result)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(payload + "\n", encoding="utf-8")
        print(payload)
        if result.ok:
            return 0
        return 2 if result.status == "BLOCKED" else 1
    if args.command == "dataplex-quality":
        payload = run_dataplex_data_quality(
            _load_yaml(args.contract),
            environment=_load_optional_yaml(args.environment),
            execute=args.execute,
            wait=args.wait,
            readback=args.readback,
            cleanup=args.cleanup,
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
        )
        body = json.dumps(payload, indent=2, sort_keys=True)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(body + "\n", encoding="utf-8")
        print(body)
        if payload["status"] in {"PLANNED_NOT_EXECUTED", "SKIPPED", "SUCCEEDED"}:
            return 0
        return 2 if payload["status"] == "BLOCKED" else 1
    if args.command == "dataplex-lineage-aspects":
        if args.lineage_only and args.aspects_only:
            raise ValueError("--lineage-only and --aspects-only cannot be combined")
        payload = run_dataplex_lineage_aspects(
            _load_yaml(args.contract),
            environment=_load_optional_yaml(args.environment),
            execute=args.execute,
            publish_lineage=not args.aspects_only,
            apply_aspects=not args.lineage_only,
            readback=args.readback,
            cleanup_aspect_type=args.cleanup_aspect_type,
            run_id=args.run_id,
        )
        body = json.dumps(payload, indent=2, sort_keys=True)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(body + "\n", encoding="utf-8")
        print(body)
        if payload["status"] in {"PLANNED_NOT_EXECUTED", "SKIPPED", "SUCCEEDED"}:
            return 0
        return 2 if payload["status"] == "BLOCKED" else 1
    if args.command == "deploy-project":
        result = deploy_gcp_project(
            args.project,
            environment=args.environment,
            environment_key=args.environment_key,
            dry_run=True,
        )
        workflow_source_path: Path | None = None
        if args.output_dir:
            _write_artifacts(args.output_dir, result.deployment_artifacts)
            workflow_source_path = args.output_dir / "deployment" / "gcp_workflows_runner.yaml"
        payload = result.to_dict(summary_only=args.summary_only)
        wants_orchestration = (
            args.render_orchestration
            or args.deploy_orchestration
            or args.run_orchestration
            or args.wait_orchestration
            or args.readback_orchestration
            or args.reset_orchestration_data
            or args.cleanup_orchestration
            or args.cleanup_orchestration_data
        )
        if wants_orchestration:
            applies_orchestration = (
                args.deploy_orchestration
                or args.run_orchestration
                or args.wait_orchestration
                or args.readback_orchestration
                or args.reset_orchestration_data
                or args.cleanup_orchestration
                or args.cleanup_orchestration_data
            )
            if args.dry_run and applies_orchestration:
                raise ValueError(
                    "--dry-run cannot be combined with --deploy-orchestration, "
                    "--run-orchestration, --wait-orchestration, --readback-orchestration, "
                    "--reset-orchestration-data, --cleanup-orchestration or --cleanup-orchestration-data"
                )
            if not applies_orchestration and workflow_source_path is None:
                source_path = Path("deployment/gcp_workflows_runner.yaml")
                payload["orchestration"] = run_gcp_workflows_orchestration(
                    workflow_manifest=json.loads(
                        result.deployment_artifacts["deployment/gcp_workflows_runner_manifest.json"]
                    ),
                    workflow_source=source_path,
                    readback_plan=json.loads(
                        result.deployment_artifacts["deployment/gcp_workflows_evidence_readback.json"]
                    ),
                    cleanup_plan=json.loads(
                        result.deployment_artifacts["deployment/gcp_workflows_cleanup_plan.json"]
                    ),
                    readback_location=args.readback_location,
                )
            else:
                with tempfile.TemporaryDirectory(prefix="contractforge-gcp-workflows-") as tmp:
                    source_path = workflow_source_path or _write_single_artifact(
                        Path(tmp),
                        "deployment/gcp_workflows_runner.yaml",
                        result.deployment_artifacts["deployment/gcp_workflows_runner.yaml"],
                    )
                    payload["orchestration"] = run_gcp_workflows_orchestration(
                        workflow_manifest=json.loads(
                            result.deployment_artifacts["deployment/gcp_workflows_runner_manifest.json"]
                        ),
                        workflow_source=source_path,
                        deploy=args.deploy_orchestration,
                        run=args.run_orchestration,
                        wait=args.wait_orchestration,
                        readback=args.readback_orchestration,
                        reset_data=args.reset_orchestration_data,
                        cleanup=args.cleanup_orchestration,
                        readback_location=args.readback_location,
                        readback_plan=json.loads(
                            result.deployment_artifacts["deployment/gcp_workflows_evidence_readback.json"]
                        ),
                        cleanup_plan=json.loads(
                            result.deployment_artifacts["deployment/gcp_workflows_cleanup_plan.json"]
                        ),
                        cleanup_data=args.cleanup_orchestration_data,
                        service_account=args.workflow_service_account,
                        execution_id=args.workflow_execution_id,
                    )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if result.ok else 2
    if args.command == "run-project":
        result = run_gcp_project_smoke(
            args.project,
            environment=args.environment,
            environment_key=args.environment_key,
            execute=args.execute,
            runtime=args.runtime,
            prepare_evidence=not args.skip_evidence_ddl,
            persist_evidence=not args.skip_evidence_write,
            run_quality=not args.skip_quality,
            enforce_schema_policy=args.enforce_schema_policy,
            allow_review_required=args.allow_review_required,
            stop_on_failure=not args.continue_on_failure,
            start_at=args.start_at,
        )
        payload = project_smoke_result_json(result)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(payload + "\n", encoding="utf-8")
        print(payload)
        return 0 if result.ok else 2
    if args.command == "source-promotion":
        contract = _load_yaml(args.contract)
        payload = run_gcp_source_promotion(
            contract.get("source"),
            environment=_load_optional_yaml(args.environment),
            execute=args.execute,
            readback=args.readback,
        )
        body = json.dumps(payload, indent=2, sort_keys=True)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(body + "\n", encoding="utf-8")
        print(body)
        if payload["status"] in {"PLANNED_NOT_EXECUTED", "SKIPPED", "SUCCEEDED"}:
            return 0
        return 1
    if args.command == "governance-reconcile":
        payload = run_bigquery_governance_reconciliation(
            _load_yaml(args.contract),
            environment=_load_optional_yaml(args.environment),
            execute=args.execute,
        )
        body = json.dumps(payload, indent=2, sort_keys=True)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(body + "\n", encoding="utf-8")
        print(body)
        if payload["status"] in {"PLANNED_NOT_EXECUTED", "SKIPPED", "SUCCEEDED"}:
            return 0
        return 1
    if args.command == "sources":
        print(json.dumps(list(list_gcp_source_support()), indent=2, sort_keys=True))
        return 0
    if args.command == "stabilization-report":
        payload = gcp_stabilization_report()
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if not args.strict_final or payload["stable_final"] is True else 1
    if args.command == "cost-report":
        env = GCPEnvironment.from_contract(_load_optional_yaml(args.environment))
        payload = build_operational_cost_report(
            project_id=args.project_id or env.project_id,
            dataset=args.dataset or env.evidence_dataset or env.dataset or "contractforge_ops",
            lookback_days=args.lookback_days,
            group_by=tuple(args.group_by) if args.group_by else None,
            cost_model=CostModel(
                bytes_processed_per_tib_rate=args.bytes_processed_per_tib_rate,
                slot_hour_rate=args.slot_hour_rate,
                currency=args.currency,
            ),
            include_failed=not args.success_only,
            query_only=True,
            limit=args.limit,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    return 2


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def _load_optional_yaml(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return _load_yaml(path)


def _planning_payload(result) -> dict[str, Any]:
    return {
        "status": result.status,
        "plan": None
        if result.plan is None
        else {
            "platform": result.plan.platform,
            "evidence_required": result.plan.evidence_required,
            "steps": [{"name": step.name, "intent": step.intent} for step in result.plan.steps],
        },
        "blockers": [{"code": blocker.code, "message": blocker.message} for blocker in result.blockers],
        "warnings": [{"code": warning.code, "message": warning.message} for warning in result.warnings],
    }


def _write_artifacts(output_dir: Path, artifacts: dict[str, str]) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name, body in sorted(artifacts.items()):
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Refusing to write unsafe artifact path: {name}")
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
        written.append(name)
    return written


def _write_single_artifact(output_dir: Path, name: str, body: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Refusing to write unsafe artifact path: {name}")
    destination = output_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
    return destination


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
