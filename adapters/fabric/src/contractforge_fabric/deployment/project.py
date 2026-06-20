"""Project-level Fabric deployment planning and execution."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import yaml
from contractforge_core.contracts import load_contract_bundle
from contractforge_core.deployment import build_deployment_ledger_record, new_deployment_id

from contractforge_fabric.deployment.ledger import render_deployment_ledger_ddl_sql, render_deployment_ledger_insert_sql
from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.runtime.factory import fabric_rest_client_from_environment
from contractforge_fabric.runtime.notebook import (
    FabricNotebookDeployment,
    definition_fingerprint,
    deploy_fabric_notebook_contract,
)
from contractforge_fabric.runtime.rest import FabricRestClient
from contractforge_fabric.smoke.project import (
    _load_mapping,
    _project_environment_path,
    _project_execution_steps,
    _project_file,
    _step_contract_path,
    _step_dependencies,
)


@dataclass(frozen=True)
class FabricProjectDeploymentStep:
    name: str
    layer: str | None
    contract: str
    depends_on: tuple[str, ...]
    notebook_name: str
    definition_hash: str
    deployment: FabricNotebookDeployment | None = None

    def to_dict(self, *, summary_only: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "layer": self.layer,
            "contract": self.contract,
            "depends_on": list(self.depends_on),
            "notebook_name": self.notebook_name,
            "definition_hash": self.definition_hash,
        }
        if self.deployment is not None:
            payload["deployment"] = asdict(self.deployment) if not summary_only else {
                "action": self.deployment.action,
                "notebook_id": self.deployment.notebook_id,
            }
        return payload


@dataclass(frozen=True)
class FabricProjectDeployment:
    deployment_id: str
    project: str
    environment: str | None
    environment_key: str
    dry_run: bool
    status: str
    strategy: str
    deployment_pipeline: dict[str, Any] | None
    git_integration: dict[str, Any] | None
    steps: tuple[FabricProjectDeploymentStep, ...]
    deployment_records: tuple[dict[str, Any], ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "SUCCEEDED"

    @property
    def deployment_artifacts(self) -> dict[str, str]:
        return {
            "deployment/fabric_project_deployment_manifest.json": json.dumps(
                self.to_dict(summary_only=False),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            "deployment/fabric_deployment_ledger.sql": _deployment_ledger_sql(self.deployment_records),
        }

    def to_dict(self, *, summary_only: bool = False) -> dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "project": self.project,
            "environment": self.environment,
            "environment_key": self.environment_key,
            "dry_run": self.dry_run,
            "status": self.status,
            "ok": self.ok,
            "strategy": self.strategy,
            "deployment_pipeline": self.deployment_pipeline,
            "git_integration": self.git_integration,
            "steps": [step.to_dict(summary_only=summary_only) for step in self.steps],
            "deployment_records": [] if summary_only else _jsonable(list(self.deployment_records)),
        }


def render_fabric_project_deployment_manifest(
    project: str | Path,
    *,
    environment: str | Path | None = None,
    environment_key: str = "fabric",
) -> dict[str, Any]:
    return deploy_fabric_project(
        project,
        environment=environment,
        environment_key=environment_key,
        dry_run=True,
    ).to_dict(summary_only=False)


def deploy_fabric_project(
    project: str | Path,
    *,
    environment: str | Path | None = None,
    environment_key: str = "fabric",
    client: FabricRestClient | None = None,
    dry_run: bool = True,
    update_existing: bool = False,
    max_attempts: int = 30,
) -> FabricProjectDeployment:
    """Plan or deploy all Fabric notebooks declared by a project, without running them."""

    project_file = _project_file(project)
    project_root = project_file.parent
    project_payload = _load_mapping(project_file, label="project")
    deployment_id = new_deployment_id()
    deployment_ts_utc = datetime.now(timezone.utc)
    environment_path = (
        Path(environment)
        if environment
        else _project_environment_path(project_payload, project_root, environment_key)
    )
    environment_payload = _load_mapping(environment_path, label="environment") if environment_path else None
    env = FabricEnvironment.from_contract(environment_payload)
    project_client = None if dry_run else client or fabric_rest_client_from_environment(env)
    deployment_settings = _project_deployment_settings(project_payload, environment_key)

    steps: list[FabricProjectDeploymentStep] = []
    deployment_records: list[dict[str, Any]] = []
    for step in _project_execution_steps(project_payload):
        contract_ref = _step_contract_path(step, environment_key)
        contract_path = project_root / contract_ref
        contract = _load_contract(contract_path)
        step_env = _step_environment(env, project_payload, step)
        step_environment_payload = _environment_payload_for_step(environment_payload, step_env)
        notebook_name = step_env.notebook_name or _notebook_name_from_contract(contract)
        rendered_deployment: FabricNotebookDeployment | None = None
        definition_hash = _definition_hash(contract, step_env)
        if project_client is not None:
            rendered_deployment = deploy_fabric_notebook_contract(
                contract,
                step_environment_payload,
                client=project_client,
                update_existing=update_existing,
            )
            rendered_deployment = _finalize_notebook_deployment(
                rendered_deployment,
                client=project_client,
                max_attempts=max_attempts,
            )
            definition_hash = rendered_deployment.definition_hash or definition_hash
        deployment_status = _step_deployment_status(rendered_deployment, dry_run=dry_run)
        action = "dry_run" if dry_run else (rendered_deployment.action if rendered_deployment else "blocked")
        deployment_records.append(
            build_deployment_ledger_record(
                deployment_id=deployment_id,
                adapter="contractforge-fabric",
                platform="fabric",
                subtarget="fabric_lakehouse",
                deployment_ts_utc=deployment_ts_utc,
                step_name=str(step.get("name") or contract_path.stem),
                project_name=str(project_payload.get("name") or ""),
                project_path=str(project_file),
                environment_key=environment_key,
                environment_path=str(environment_path) if environment_path else None,
                contract_name=str(step.get("name") or contract_path.stem),
                contract_path=str(contract_path),
                contract_layer=str(step["layer"]) if step.get("layer") is not None else None,
                target_table=_target_table(contract),
                mode=str(contract.get("mode") or ""),
                action=action,
                deployment_status=deployment_status,
                artifact_kind="fabric_notebook",
                artifact_name=notebook_name,
                artifact_id=rendered_deployment.notebook_id if rendered_deployment else None,
                definition_hash=definition_hash,
                previous_definition_hash=rendered_deployment.previous_definition_hash if rendered_deployment else None,
                contract_payload=contract,
                environment_payload=step_environment_payload,
                manifest_payload={
                    "project": str(project_file),
                    "step": step,
                    "notebook_name": notebook_name,
                    "definition_hash": definition_hash,
                },
                package_versions=_package_versions(),
                git_commit=_git_commit(),
                deployed_by=_deployed_by(),
                deployment_config={
                    "dry_run": dry_run,
                    "update_existing": update_existing,
                    "max_attempts": max_attempts,
                },
                deployment_result=asdict(rendered_deployment) if rendered_deployment else {"action": action},
                framework_version=_package_versions().get("contractforge-fabric"),
            )
        )
        steps.append(
            FabricProjectDeploymentStep(
                name=str(step.get("name") or contract_path.stem),
                layer=str(step["layer"]) if step.get("layer") is not None else None,
                contract=str(contract_path),
                depends_on=_step_dependencies(step),
                notebook_name=notebook_name,
                definition_hash=definition_hash,
                deployment=rendered_deployment,
            )
        )

    status = "SUCCEEDED" if steps and all(_deployment_step_ok(step, dry_run=dry_run) for step in steps) else "BLOCKED"
    return FabricProjectDeployment(
        deployment_id=deployment_id,
        project=str(project_file),
        environment=str(environment_path) if environment_path else None,
        environment_key=environment_key,
        dry_run=dry_run,
        status=status,
        strategy=str(deployment_settings.get("strategy") or "notebook_definition"),
        deployment_pipeline=_mapping_or_none(deployment_settings.get("deployment_pipeline")),
        git_integration=_mapping_or_none(deployment_settings.get("git_integration")),
        steps=tuple(steps),
        deployment_records=tuple(deployment_records),
    )


def _load_contract(path: Path) -> dict[str, Any]:
    bundle = load_contract_bundle(_bundle_base(path))
    return bundle.contract


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
        ".environment.yaml",
        ".environment.yml",
        ".environment.json",
    )
    name = path.name
    for suffix in suffixes:
        if name.endswith(suffix):
            return path.with_name(name[: -len(suffix)])
    return path


def _project_deployment_settings(project: dict[str, Any], environment_key: str) -> dict[str, Any]:
    deployment = project.get("deployment")
    if not isinstance(deployment, dict):
        return {}
    fabric = deployment.get(environment_key)
    if isinstance(fabric, dict):
        return dict(fabric)
    return dict(deployment.get("fabric")) if isinstance(deployment.get("fabric"), dict) else {}


def _step_environment(base: FabricEnvironment, project: dict[str, Any], step: dict[str, Any]) -> FabricEnvironment:
    return FabricEnvironment(
        workspace_id=base.workspace_id,
        workspace_name=base.workspace_name,
        tenant_id=base.tenant_id,
        tenant_domain=base.tenant_domain,
        lakehouse_id=base.lakehouse_id,
        lakehouse_name=base.lakehouse_name,
        warehouse_id=base.warehouse_id,
        warehouse_name=base.warehouse_name,
        evidence_lakehouse=base.evidence_lakehouse,
        evidence_schema=base.evidence_schema,
        artifact_uri=base.artifact_uri,
        runtime_kind=base.runtime_kind,
        notebook_id=None,
        notebook_name=str(step.get("notebook_name") or "") or _default_step_notebook_name(project, step),
        pipeline_id=base.pipeline_id,
        secret_vault_url=base.secret_vault_url,
        secret_scopes=base.secret_scopes,
    )


def _environment_payload_for_step(base: dict[str, Any] | None, env: FabricEnvironment) -> dict[str, Any]:
    payload = yaml.safe_load(yaml.safe_dump(base or {}, sort_keys=False))
    if not isinstance(payload, dict):
        payload = {}
    parameters = payload.setdefault("parameters", {})
    fabric = parameters.setdefault("fabric", {})
    if env.notebook_name:
        fabric["notebook_name"] = env.notebook_name
    fabric.pop("notebook_id", None)
    return payload


def _notebook_name_from_contract(contract: dict[str, Any]) -> str:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_fabric.rendering.definition import render_notebook_item_definition

    rendered = json.loads(render_notebook_item_definition(semantic_contract_from_mapping(contract), FabricEnvironment()))
    return str(rendered["create_notebook_request"]["displayName"])


def _default_step_notebook_name(project: dict[str, Any], step: dict[str, Any]) -> str:
    project_name = str(project.get("name") or "project")
    step_name = str(step.get("name") or "step")
    raw = f"cf_{project_name}_{step_name}"
    return re.sub(r"[^A-Za-z0-9 _.-]+", "_", raw).replace(".", "_")[:128]


def _definition_hash(contract: dict[str, Any], env: FabricEnvironment) -> str:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_fabric.rendering.definition import render_notebook_item_definition

    rendered = json.loads(render_notebook_item_definition(semantic_contract_from_mapping(contract), env))
    return definition_fingerprint(rendered["create_notebook_request"]["definition"])


def _deployment_step_ok(step: FabricProjectDeploymentStep, *, dry_run: bool) -> bool:
    if dry_run:
        return True
    return step.deployment is not None and step.deployment.action in {"created", "updated", "unchanged", "exists"}


def _step_deployment_status(deployment: FabricNotebookDeployment | None, *, dry_run: bool) -> str:
    if dry_run:
        return "PLANNED"
    if deployment is None:
        return "BLOCKED"
    if deployment.action in {"created", "updated", "unchanged", "exists"}:
        return "SUCCEEDED"
    return "BLOCKED"


def _finalize_notebook_deployment(
    deployment: FabricNotebookDeployment,
    *,
    client: FabricRestClient,
    max_attempts: int,
) -> FabricNotebookDeployment:
    if deployment.operation is not None:
        client.poll_operation(deployment.operation, max_attempts=max_attempts)
    if deployment.notebook_id is None and deployment.action in {"created", "updated", "unchanged", "exists"}:
        return replace(
            deployment,
            notebook_id=client.resolve_item_id(item_type="Notebook", display_name=deployment.display_name),
        )
    return deployment


def _mapping_or_none(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _target_table(contract: dict[str, Any]) -> str | None:
    target = contract.get("target")
    if not isinstance(target, dict):
        return None
    parts = [str(target.get(key)) for key in ("catalog", "schema", "table") if target.get(key)]
    return ".".join(parts) if parts else None


def _deployment_ledger_sql(records: tuple[dict[str, Any], ...]) -> str:
    statements = [render_deployment_ledger_ddl_sql()]
    statements.extend(render_deployment_ledger_insert_sql(record) for record in records)
    return "\n\n".join(statement.rstrip("; \n") + ";" for statement in statements if statement.strip()) + "\n"


def _package_versions() -> dict[str, str]:
    packages = ("contractforge-core", "contractforge-fabric")
    versions: dict[str, str] = {}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "0.0.0+unknown"
    return versions


def _git_commit() -> str | None:
    return os.environ.get("GITHUB_SHA") or os.environ.get("CF_GIT_COMMIT") or os.environ.get("GIT_COMMIT")


def _deployed_by() -> str | None:
    return os.environ.get("GITHUB_ACTOR") or os.environ.get("USER") or os.environ.get("USERNAME")


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
