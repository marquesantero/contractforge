"""GCP project-level smoke workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from contractforge_core.contracts import load_contract_bundle

from contractforge_gcp.runtime import BigQueryRuntimeClient, bigquery_runtime_client_from_environment
from contractforge_gcp.smoke.workflow import GCPContractSmokeResult, run_gcp_contract_smoke
from contractforge_gcp.environment import GCPEnvironment


@dataclass(frozen=True)
class GCPProjectSmokeStepResult:
    name: str
    layer: str | None
    contract: str
    depends_on: tuple[str, ...]
    expected_result: str
    result: GCPContractSmokeResult

    @property
    def status(self) -> str:
        return self.result.status

    @property
    def ok(self) -> bool:
        return _matches_expected_result(self.status, self.expected_result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "layer": self.layer,
            "contract": self.contract,
            "depends_on": list(self.depends_on),
            "expected_result": self.expected_result,
            "status": self.status,
            "ok": self.ok,
            "result": self.result.to_dict(),
        }


@dataclass(frozen=True)
class GCPProjectSmokeResult:
    project: str
    environment: str | None
    environment_key: str
    executed: bool
    start_at: str | None
    status: str
    steps: tuple[GCPProjectSmokeStepResult, ...]

    @property
    def ok(self) -> bool:
        return self.status == "SUCCEEDED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "environment": self.environment,
            "environment_key": self.environment_key,
            "executed": self.executed,
            "start_at": self.start_at,
            "status": self.status,
            "ok": self.ok,
            "steps": [step.to_dict() for step in self.steps],
        }


def run_gcp_project_smoke(
    project: str | Path,
    *,
    environment: str | Path | None = None,
    environment_key: str = "gcp",
    client: BigQueryRuntimeClient | None = None,
    execute: bool = False,
    runtime: str = "auto",
    prepare_evidence: bool = True,
    persist_evidence: bool = True,
    run_quality: bool = True,
    enforce_schema_policy: bool = False,
    allow_review_required: bool = False,
    stop_on_failure: bool = True,
    start_at: str | None = None,
) -> GCPProjectSmokeResult:
    """Run every GCP contract declared by a ContractForge project in order."""

    project_file = _project_file(project)
    project_root = project_file.parent
    project_payload = _load_mapping(project_file, label="project")
    environment_path = (
        Path(environment)
        if environment
        else _project_environment_path(project_payload, project_root, environment_key)
    )
    environment_payload = _load_mapping(environment_path, label="environment") if environment_path else None
    runtime_client = (
        client
        if client is not None or not execute
        else bigquery_runtime_client_from_environment(GCPEnvironment.from_contract(environment_payload), runtime=runtime)
    )

    results: list[GCPProjectSmokeStepResult] = []
    for step in _steps_from(_project_execution_steps(project_payload), start_at=start_at):
        contract_ref = _step_contract_path(step, environment_key)
        contract_path = project_root / contract_ref
        contract, bundle_environment = _load_contract_input(contract_path)
        effective_environment = environment_payload or bundle_environment
        if effective_environment is None:
            raise ValueError(f"GCP project step {step.get('name') or contract_path.stem!r} requires an environment")
        expected_result = _step_expected_result(step, default="succeeded" if execute else "dry_run")
        result = run_gcp_contract_smoke(
            contract,
            effective_environment,
            client=runtime_client,
            execute=execute,
            runtime=runtime,
            prepare_evidence=prepare_evidence,
            persist_evidence=persist_evidence,
            run_quality=run_quality,
            enforce_schema_policy=enforce_schema_policy,
            allow_review_required=allow_review_required,
        )
        step_result = GCPProjectSmokeStepResult(
            name=str(step.get("name") or contract_path.stem),
            layer=str(step["layer"]) if step.get("layer") is not None else None,
            contract=str(contract_path),
            depends_on=_step_dependencies(step),
            expected_result=expected_result,
            result=result,
        )
        results.append(step_result)
        if stop_on_failure and not step_result.ok:
            break

    return GCPProjectSmokeResult(
        project=str(project_file),
        environment=str(environment_path) if environment_path else None,
        environment_key=environment_key,
        executed=execute,
        start_at=start_at,
        status=_project_status(tuple(results)),
        steps=tuple(results),
    )


def project_smoke_result_json(result: GCPProjectSmokeResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True)


def _project_file(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate / "project.yaml" if candidate.is_dir() else candidate


def _project_environment_path(project: dict[str, Any], project_root: Path, environment_key: str) -> Path | None:
    environments = project.get("environments")
    if not isinstance(environments, dict):
        return None
    if environment_key not in environments:
        raise ValueError(f"project.environments must declare {environment_key!r}")
    return project_root / str(environments[environment_key])


def _project_execution_steps(project: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    steps = project.get("execution_order")
    if not isinstance(steps, list) or not steps:
        raise ValueError("project.execution_order must be a non-empty list")
    if not all(isinstance(step, dict) for step in steps):
        raise ValueError("project.execution_order entries must be objects")
    return tuple(steps)


def _steps_from(steps: tuple[dict[str, Any], ...], *, start_at: str | None) -> tuple[dict[str, Any], ...]:
    if not start_at:
        return steps
    for index, step in enumerate(steps):
        if str(step.get("name") or "") == start_at:
            return steps[index:]
    raise ValueError(f"project.execution_order does not contain start_at step {start_at!r}")


def _step_contract_path(step: dict[str, Any], environment_key: str) -> Path:
    contracts = step.get("contracts")
    if not isinstance(contracts, dict) or environment_key not in contracts:
        name = step.get("name") or "<unnamed>"
        raise ValueError(f"project step {name!r} must declare contracts.{environment_key}")
    return Path(str(contracts[environment_key]))


def _step_dependencies(step: dict[str, Any]) -> tuple[str, ...]:
    value = step.get("depends_on")
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    name = step.get("name") or "<unnamed>"
    raise ValueError(f"project step {name!r} depends_on must be a string or list of strings")


def _step_expected_result(step: dict[str, Any], *, default: str) -> str:
    value = str(step.get("expected_result") or default).lower()
    if value not in {"succeeded", "failed", "blocked", "dry_run"}:
        name = step.get("name") or "<unnamed>"
        raise ValueError(
            f"project step {name!r} expected_result must be one of: succeeded, failed, blocked, dry_run"
        )
    return value


def _load_contract_input(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if path.is_dir() or _looks_like_split_contract(path):
        bundle = load_contract_bundle(_bundle_base(path))
        environment = bundle.environment if isinstance(bundle.environment, dict) else None
        return bundle.contract, environment
    return _load_mapping(path, label="contract"), None


def _looks_like_split_contract(path: Path) -> bool:
    return any(marker in path.name for marker in (".ingestion.", ".annotations.", ".operations.", ".access."))


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
    for suffix in suffixes:
        if path.name.endswith(suffix):
            return path.with_name(path.name[: -len(suffix)])
    return path


def _load_mapping(path: Path, *, label: str) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} file must contain a YAML mapping: {path}")
    return loaded


def _project_status(steps: tuple[GCPProjectSmokeStepResult, ...]) -> str:
    if not steps:
        return "BLOCKED"
    if all(step.ok for step in steps):
        return "SUCCEEDED"
    statuses = {step.status for step in steps}
    if "BLOCKED" in statuses:
        return "BLOCKED"
    return "FAILED"


def _matches_expected_result(status: str, expected_result: str) -> bool:
    normalized = status.upper()
    if expected_result == "succeeded":
        return normalized == "SUCCEEDED"
    if expected_result == "failed":
        return normalized == "FAILED"
    if expected_result == "blocked":
        return normalized == "BLOCKED"
    if expected_result == "dry_run":
        return normalized == "DRY_RUN"
    return False


__all__ = [
    "GCPProjectSmokeResult",
    "GCPProjectSmokeStepResult",
    "project_smoke_result_json",
    "run_gcp_project_smoke",
]
