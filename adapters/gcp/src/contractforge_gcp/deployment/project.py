"""Project-level GCP deployment planning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from contractforge_core.contracts import load_contract_bundle

from contractforge_gcp.api import plan_gcp_contract, render_gcp_contract
from contractforge_gcp.deployment.workflows import (
    GCPWorkflowOperation,
    GCPWorkflowReadbackTarget,
    render_gcp_workflows_cleanup_plan,
    render_gcp_workflows_evidence_readback_plan,
    render_gcp_workflows_execution_plan,
    render_gcp_workflows_runner_manifest,
    render_gcp_workflows_runner_yaml,
    workflow_name,
)
from contractforge_gcp.environment import GCPEnvironment


@dataclass(frozen=True)
class GCPProjectDeploymentStep:
    name: str
    layer: str | None
    contract: str
    contract_name: str
    depends_on: tuple[str, ...]
    planning_status: str
    target_table: str | None
    artifact_count: int
    deployment_manifest: str | None
    blockers: tuple[dict[str, str], ...]
    warnings: tuple[dict[str, str], ...]

    def to_dict(self, *, summary_only: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "layer": self.layer,
            "contract": self.contract,
            "contract_name": self.contract_name,
            "depends_on": list(self.depends_on),
            "planning_status": self.planning_status,
            "target_table": self.target_table,
            "artifact_count": self.artifact_count,
            "deployment_manifest": self.deployment_manifest,
        }
        if not summary_only:
            payload["blockers"] = list(self.blockers)
            payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class GCPProjectDeployment:
    project: str
    environment: str | None
    environment_key: str
    dry_run: bool
    status: str
    orchestration_included: bool
    orchestration_status: str
    orchestration_note: str
    steps: tuple[GCPProjectDeploymentStep, ...]
    deployment_artifacts: dict[str, str]

    @property
    def ok(self) -> bool:
        return self.status in {"SUCCEEDED", "REVIEW_REQUIRED"}

    def to_dict(self, *, summary_only: bool = False) -> dict[str, Any]:
        return {
            "project": self.project,
            "environment": self.environment,
            "environment_key": self.environment_key,
            "dry_run": self.dry_run,
            "status": self.status,
            "ok": self.ok,
            "orchestration_included": self.orchestration_included,
            "orchestration_status": self.orchestration_status,
            "orchestration_note": self.orchestration_note,
            "steps": [step.to_dict(summary_only=summary_only) for step in self.steps],
            "deployment_artifacts": sorted(self.deployment_artifacts),
        }


def render_gcp_project_deployment_manifest(
    project: str | Path,
    *,
    environment: str | Path | None = None,
    environment_key: str = "gcp",
) -> dict[str, Any]:
    return deploy_gcp_project(
        project,
        environment=environment,
        environment_key=environment_key,
        dry_run=True,
    ).to_dict(summary_only=False)


def deploy_gcp_project(
    project: str | Path,
    *,
    environment: str | Path | None = None,
    environment_key: str = "gcp",
    dry_run: bool = True,
) -> GCPProjectDeployment:
    """Render per-contract GCP bundles and a project deployment manifest."""

    if not dry_run:
        raise ValueError(
            "contractforge-gcp deploy-project is dry-run only until a reusable Google Cloud "
            "orchestration runner is separately certified."
        )

    project_file = _project_file(project)
    project_root = project_file.parent
    project_payload = _load_mapping(project_file, label="project")
    environment_path = (
        Path(environment)
        if environment
        else _project_environment_path(project_payload, project_root, environment_key)
    )
    environment_payload = _load_mapping(environment_path, label="environment") if environment_path else None

    steps: list[GCPProjectDeploymentStep] = []
    deployment_artifacts: dict[str, str] = {}
    workflow_operations: list[GCPWorkflowOperation] = []
    readback_targets: list[GCPWorkflowReadbackTarget] = []
    for step in _project_execution_steps(project_payload):
        contract_ref = _step_contract_path(step, environment_key)
        contract_path = project_root / contract_ref
        contract = _load_contract(contract_path)
        planning = plan_gcp_contract(contract, environment=environment_payload)
        rendered = render_gcp_contract(contract, environment=environment_payload)
        artifact_names = sorted(rendered.artifacts)
        artifact_prefix = _step_artifact_prefix(str(step.get("name") or contract_path.stem))
        step_name = str(step.get("name") or contract_path.stem)
        contract_name = _contract_name(contract, contract_path)
        target_table = _target_table(contract, environment_payload)
        for artifact_name, artifact_body in rendered.artifacts.items():
            deployment_artifacts[f"deployment/{artifact_prefix}/{artifact_name}"] = artifact_body
        manifest_name = next((name for name in artifact_names if name.endswith(".gcp.deployment_manifest.json")), None)
        if manifest_name:
            workflow_operations.extend(
                _workflow_operations(
                    step_name=str(step.get("name") or contract_path.stem),
                    contract_name=contract_name,
                    artifact_prefix=artifact_prefix,
                    deployment_manifest=rendered.artifacts[manifest_name],
                    deployment_artifacts=deployment_artifacts,
                )
            )
        steps.append(
            GCPProjectDeploymentStep(
                name=step_name,
                layer=str(step["layer"]) if step.get("layer") is not None else None,
                contract=str(contract_path),
                contract_name=contract_name,
                depends_on=_step_dependencies(step),
                planning_status=planning.status,
                target_table=target_table,
                artifact_count=len(artifact_names),
                deployment_manifest=None if manifest_name is None else f"deployment/{artifact_prefix}/{manifest_name}",
                blockers=tuple({"code": blocker.code, "message": blocker.message} for blocker in planning.blockers),
                warnings=tuple({"code": warning.code, "message": warning.message} for warning in planning.warnings),
            )
        )
        if target_table:
            readback_targets.append(
                GCPWorkflowReadbackTarget(
                    step_name=step_name,
                    contract_name=contract_name,
                    target_table=target_table,
                )
            )

    status = _project_status(steps)
    project_name = str(project_payload.get("name") or project_file.stem)
    workflows_location = _workflows_location(project_payload, environment_payload)
    workflows_project = _workflow_project_id(environment_payload, steps)
    workflows_evidence_dataset = _workflow_evidence_dataset(environment_payload)
    workflows_bigquery_location = _workflow_bigquery_location(environment_payload)
    workflows_name = workflow_name(project_name)
    result = GCPProjectDeployment(
        project=str(project_file),
        environment=str(environment_path) if environment_path else None,
        environment_key=environment_key,
        dry_run=True,
        status=status,
        orchestration_included=True,
        orchestration_status="CERTIFIED_FOR_STABLE_SURFACE",
        orchestration_note=(
            "This dry-run renders per-contract BigQuery bundles and a Google Workflows source plan with "
            "bounded BigQuery job polling and connector retry blocks. The adapter-owned Workflows "
            "deploy/run/wait/readback/reset/cleanup command path is certified for the stable GCP "
            "BigQuery batch surface."
        ),
        steps=tuple(steps),
        deployment_artifacts=deployment_artifacts,
    )
    operations = tuple(workflow_operations)
    result.deployment_artifacts["deployment/gcp_workflows_runner.yaml"] = render_gcp_workflows_runner_yaml(
        project_name=project_name,
        project_id=workflows_project,
        operations=operations,
    )
    result.deployment_artifacts["deployment/gcp_workflows_runner_manifest.json"] = (
        render_gcp_workflows_runner_manifest(
            project_name=project_name,
            project_id=workflows_project,
            location=workflows_location,
            workflow_name=workflows_name,
            operations=operations,
        )
    )
    result.deployment_artifacts["deployment/gcp_workflows_execution_plan.json"] = render_gcp_workflows_execution_plan(
        project_name=project_name,
        project_id=workflows_project,
        location=workflows_location,
        workflow_name=workflows_name,
    )
    result.deployment_artifacts["deployment/gcp_workflows_evidence_readback.json"] = (
        render_gcp_workflows_evidence_readback_plan(
            project_name=project_name,
            project_id=workflows_project,
            evidence_dataset=workflows_evidence_dataset,
            targets=tuple(readback_targets),
            location=workflows_bigquery_location,
        )
    )
    result.deployment_artifacts["deployment/gcp_workflows_cleanup_plan.json"] = render_gcp_workflows_cleanup_plan(
        project_name=project_name,
        project_id=workflows_project,
        evidence_dataset=workflows_evidence_dataset,
        targets=tuple(readback_targets),
        location=workflows_bigquery_location,
    )
    result.deployment_artifacts["deployment/gcp_project_deployment_manifest.json"] = (
        json.dumps(result.to_dict(summary_only=False), indent=2, sort_keys=True) + "\n"
    )
    return result


def project_deployment_json(deployment: GCPProjectDeployment, *, summary_only: bool = False) -> str:
    return json.dumps(deployment.to_dict(summary_only=summary_only), indent=2, sort_keys=True)


def _project_file(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate / "project.yaml" if candidate.is_dir() else candidate


def _load_mapping(path: Path, *, label: str) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} file must contain a YAML mapping: {path}")
    return loaded


def _project_environment_path(project: dict[str, Any], project_root: Path, environment_key: str) -> Path | None:
    environments = project.get("environments")
    if not isinstance(environments, dict) or environment_key not in environments:
        return None
    return project_root / str(environments[environment_key])


def _project_execution_steps(project: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    steps = project.get("execution_order")
    if not isinstance(steps, list) or not steps:
        raise ValueError("project.execution_order must be a non-empty list")
    if not all(isinstance(step, dict) for step in steps):
        raise ValueError("project.execution_order entries must be objects")
    return tuple(steps)


def _step_contract_path(step: dict[str, Any], environment_key: str) -> Path:
    contracts = step.get("contracts")
    if not isinstance(contracts, dict) or environment_key not in contracts:
        raise ValueError(f"project.execution_order step requires contracts.{environment_key}")
    return Path(str(contracts[environment_key]))


def _step_dependencies(step: dict[str, Any]) -> tuple[str, ...]:
    value = step.get("depends_on") or step.get("after") or ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item).strip())
    return ()


def _load_contract(path: Path) -> dict[str, Any]:
    return load_contract_bundle(_bundle_base(path)).contract


def _bundle_base(path: Path) -> Path:
    suffixes = (
        ".ingestion.yaml",
        ".ingestion.yml",
        ".ingestion.json",
        ".annotations.yaml",
        ".annotations.yml",
        ".annotations.json",
        ".operations.yaml",
        ".operations.yml",
        ".operations.json",
        ".access.yaml",
        ".access.yml",
        ".access.json",
    )
    for suffix in suffixes:
        if path.name.endswith(suffix):
            return path.with_name(path.name[: -len(suffix)])
    return path


def _target_table(contract: dict[str, Any], environment_payload: dict[str, Any] | None) -> str | None:
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    if not target:
        return None
    env = GCPEnvironment.from_contract(environment_payload)
    project_id = target.get("catalog") or env.project_id
    dataset = target.get("schema") or env.dataset
    table = target.get("table")
    if not project_id or not dataset or not table:
        return None
    return f"{project_id}.{dataset}.{table}"


def _contract_name(contract: dict[str, Any], contract_path: Path) -> str:
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    for value in (target.get("name"), target.get("table")):
        if value:
            return str(value)
    return contract_path.stem


def _workflow_operations(
    *,
    step_name: str,
    contract_name: str,
    artifact_prefix: str,
    deployment_manifest: str,
    deployment_artifacts: dict[str, str],
) -> tuple[GCPWorkflowOperation, ...]:
    manifest = json.loads(deployment_manifest)
    target = manifest.get("target") if isinstance(manifest.get("target"), dict) else {}
    operations: list[GCPWorkflowOperation] = []
    for apply_step in manifest.get("apply_order", ()):
        if not isinstance(apply_step, dict) or "artifact" not in apply_step:
            continue
        artifact = f"deployment/{artifact_prefix}/{apply_step['artifact']}"
        body = deployment_artifacts.get(artifact)
        if body is None:
            continue
        operations.append(
            GCPWorkflowOperation(
                step_name=step_name,
                operation_name=str(apply_step.get("name") or "operation"),
                operation=str(apply_step.get("operation") or "REVIEW"),
                artifact=artifact,
                body=body,
                contract_name=contract_name,
                target_table=str(target["table"]) if target.get("table") else None,
                evidence_dataset=str(manifest["evidence_dataset"]) if manifest.get("evidence_dataset") else None,
            )
        )
    return tuple(operations)


def _workflow_project_id(
    environment_payload: dict[str, Any] | None,
    steps: list[GCPProjectDeploymentStep],
) -> str:
    env = GCPEnvironment.from_contract(environment_payload)
    if env.project_id:
        return env.project_id
    for step in steps:
        if step.target_table and "." in step.target_table:
            return step.target_table.split(".", 1)[0]
    return "UNSPECIFIED_PROJECT"


def _workflow_evidence_dataset(environment_payload: dict[str, Any] | None) -> str:
    env = GCPEnvironment.from_contract(environment_payload)
    return env.evidence_dataset or env.dataset or "contractforge_ops"


def _workflow_bigquery_location(environment_payload: dict[str, Any] | None) -> str:
    env = GCPEnvironment.from_contract(environment_payload)
    return env.location or "US"


def _workflows_location(project: dict[str, Any], environment_payload: dict[str, Any] | None) -> str:
    deployment = project.get("deployment") if isinstance(project.get("deployment"), dict) else {}
    gcp = deployment.get("gcp") if isinstance(deployment.get("gcp"), dict) else {}
    workflows = gcp.get("workflows") if isinstance(gcp.get("workflows"), dict) else {}
    for value in (
        workflows.get("location"),
        gcp.get("workflows_location"),
        gcp.get("location"),
        _environment_gcp_value(environment_payload, "workflows_location"),
    ):
        if value:
            return str(value)
    return "us-central1"


def _environment_gcp_value(environment_payload: dict[str, Any] | None, key: str) -> str | None:
    payload = environment_payload or {}
    parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    gcp = parameters.get("gcp") if isinstance(parameters.get("gcp"), dict) else {}
    value = gcp.get(key)
    return str(value) if value else None


def _step_artifact_prefix(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value).strip("_") or "step"


def _project_status(steps: list[GCPProjectDeploymentStep]) -> str:
    statuses = {step.planning_status for step in steps}
    if not steps or "UNSUPPORTED" in statuses:
        return "BLOCKED"
    if "REVIEW_REQUIRED" in statuses:
        return "REVIEW_REQUIRED"
    return "SUCCEEDED"
