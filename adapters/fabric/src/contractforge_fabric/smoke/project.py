"""Fabric project-level smoke workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from contractforge_core.contracts import load_contract_bundle

from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.runtime.factory import fabric_rest_client_from_environment
from contractforge_fabric.runtime.rest import FabricRestClient
from contractforge_fabric.smoke.workflow import FabricContractSmokeResult, run_fabric_contract_smoke


@dataclass(frozen=True)
class FabricProjectSmokeStepResult:
    name: str
    layer: str | None
    contract: str
    depends_on: tuple[str, ...]
    expected_result: str
    result: FabricContractSmokeResult

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
class FabricProjectSetupResult:
    name: str
    type: str
    status: str
    details: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status == "SUCCEEDED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "ok": self.ok,
            "details": self.details,
        }


@dataclass(frozen=True)
class FabricProjectSmokeResult:
    project: str
    environment: str | None
    environment_key: str
    wait: bool
    start_at: str | None
    status: str
    setups: tuple[FabricProjectSetupResult, ...]
    steps: tuple[FabricProjectSmokeStepResult, ...]

    @property
    def ok(self) -> bool:
        return self.status == "SUCCEEDED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "environment": self.environment,
            "environment_key": self.environment_key,
            "wait": self.wait,
            "start_at": self.start_at,
            "status": self.status,
            "ok": self.ok,
            "setups": [setup.to_dict() for setup in self.setups],
            "steps": [step.to_dict() for step in self.steps],
        }


def run_fabric_project_smoke(
    project: str | Path,
    *,
    environment: str | Path | None = None,
    environment_key: str = "fabric",
    client: FabricRestClient | None = None,
    wait: bool = True,
    max_attempts: int = 30,
    retry_after_seconds: int | None = None,
    stop_on_failure: bool = True,
    start_at: str | None = None,
) -> FabricProjectSmokeResult:
    """Run every Fabric contract declared by a ContractForge project."""

    project_file = _project_file(project)
    project_root = project_file.parent
    project_payload = _load_mapping(project_file, label="project")
    environment_path = (
        Path(environment)
        if environment
        else _project_environment_path(project_payload, project_root, environment_key)
    )
    environment_payload = _load_mapping(environment_path, label="environment") if environment_path else None
    project_client = client
    setup_results: tuple[FabricProjectSetupResult, ...] = ()
    if _project_shortcut_setups(project_payload):
        if environment_payload is None:
            raise ValueError("Fabric project setup requires an environment")
        env = FabricEnvironment.from_contract(environment_payload)
        project_client = project_client or fabric_rest_client_from_environment(env)
        setup_results = _run_project_setups(
            project_payload,
            env,
            raw_environment=environment_payload,
            client=project_client,
        )

    results: list[FabricProjectSmokeStepResult] = []
    steps = _project_execution_steps(project_payload)
    selected_steps = _steps_from(steps, start_at=start_at)
    for step in selected_steps:
        contract_ref = _step_contract_path(step, environment_key)
        contract_path = project_root / contract_ref
        contract, bundle_environment = _load_contract_input(contract_path)
        effective_environment = environment_payload or bundle_environment
        expected_result = _step_expected_result(step)
        if effective_environment is None:
            raise ValueError(f"Fabric project step {step.get('name') or contract_path.stem!r} requires an environment")
        result = run_fabric_contract_smoke(
            contract,
            effective_environment,
            client=project_client,
            wait=wait,
            max_attempts=max_attempts,
            retry_after_seconds=retry_after_seconds,
        )
        step_result = FabricProjectSmokeStepResult(
            name=str(step.get("name") or contract_path.stem),
            layer=str(step["layer"]) if step.get("layer") is not None else None,
            contract=str(contract_path),
            depends_on=_step_dependencies(step),
            expected_result=expected_result,
            result=result,
        )
        results.append(step_result)
        if stop_on_failure and not _step_continues(step_result, wait=wait):
            break

    status = _project_status(tuple(results), wait=wait)
    if setup_results and not all(setup.ok for setup in setup_results):
        status = "BLOCKED"
    return FabricProjectSmokeResult(
        project=str(project_file),
        environment=str(environment_path) if environment_path else None,
        environment_key=environment_key,
        wait=wait,
        start_at=start_at,
        status=status,
        setups=setup_results,
        steps=tuple(results),
    )


def _run_project_setups(
    project: dict[str, Any],
    environment: FabricEnvironment,
    *,
    raw_environment: dict[str, Any],
    client: FabricRestClient,
) -> tuple[FabricProjectSetupResult, ...]:
    results: list[FabricProjectSetupResult] = []
    for raw_shortcut in _project_shortcut_setups(project):
        shortcut = _resolve_setup_value(raw_shortcut, raw_environment)
        item_id = str(shortcut.get("item_id") or environment.lakehouse_id or "")
        if not item_id:
            raise ValueError(f"Fabric shortcut setup {shortcut.get('name') or '<unnamed>'!r} requires lakehouse_id")
        name = str(shortcut.get("name") or "")
        path = str(shortcut.get("path") or "")
        target = shortcut.get("target")
        if not name or not path or not isinstance(target, dict):
            raise ValueError("Fabric shortcut setup entries require name, path and target")
        response = client.create_shortcut(
            item_id=item_id,
            path=path,
            name=name,
            target=target,
            conflict_policy=str(shortcut.get("conflict_policy") or "CreateOrOverwrite"),
        )
        results.append(
            FabricProjectSetupResult(
                name=name,
                type="shortcut",
                status="SUCCEEDED",
                details={
                    "path": path,
                    "target_type": _shortcut_target_type(target),
                    "response": response,
                },
            )
        )
    return tuple(results)


def _project_shortcut_setups(project: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    setup = project.get("fabric_setup")
    if not isinstance(setup, dict):
        return ()
    shortcuts = setup.get("shortcuts")
    if shortcuts is None:
        return ()
    if not isinstance(shortcuts, list) or not all(isinstance(shortcut, dict) for shortcut in shortcuts):
        raise ValueError("project.fabric_setup.shortcuts must be a list of objects")
    return tuple(shortcuts)


def _shortcut_target_type(target: dict[str, Any]) -> str:
    if len(target) == 1:
        return next(iter(target))
    return "unknown"


_PARAMETER_PLACEHOLDER_RE = re.compile(r"\{\{\s*parameter:([^}]+)\}\}", re.IGNORECASE)


def _resolve_setup_value(value: Any, environment: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_setup_value(item, environment) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_setup_value(item, environment) for item in value]
    if isinstance(value, str):
        return _PARAMETER_PLACEHOLDER_RE.sub(
            lambda match: str(_lookup_parameter(environment, match.group(1).strip())),
            value,
        )
    return value


def _lookup_parameter(environment: dict[str, Any], path: str) -> Any:
    current: Any = environment.get("parameters", {})
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Unknown project setup parameter placeholder {path!r}")
        current = current[part]
    return current


def _project_status(steps: tuple[FabricProjectSmokeStepResult, ...], *, wait: bool) -> str:
    if not steps:
        return "BLOCKED"
    if all(step.ok for step in steps):
        return "SUCCEEDED"
    statuses = {step.status for step in steps}
    if not wait and statuses <= {"RUNNING", "SUCCEEDED"}:
        return "RUNNING"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    return "FAILED"


def _step_continues(step: FabricProjectSmokeStepResult, *, wait: bool) -> bool:
    return step.ok or (not wait and step.expected_result == "succeeded" and step.status == "RUNNING")


def _matches_expected_result(status: str, expected_result: str) -> bool:
    expected = expected_result.lower()
    normalized = status.upper()
    if expected == "succeeded":
        return normalized == "SUCCEEDED"
    if expected == "failed":
        return normalized == "FAILED"
    if expected == "blocked":
        return normalized == "BLOCKED"
    if expected == "running":
        return normalized == "RUNNING"
    return False


def _project_file(project: str | Path) -> Path:
    path = Path(project)
    return path / "project.yaml" if path.is_dir() else path


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


def _step_contract_path(step: dict[str, Any], environment_key: str) -> str:
    contracts = step.get("contracts")
    if not isinstance(contracts, dict) or environment_key not in contracts:
        name = step.get("name") or "<unnamed>"
        raise ValueError(f"project step {name!r} must declare contracts.{environment_key}")
    return str(contracts[environment_key])


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


def _step_expected_result(step: dict[str, Any]) -> str:
    value = str(step.get("expected_result") or "succeeded").lower()
    if value not in {"succeeded", "failed", "blocked", "running"}:
        name = step.get("name") or "<unnamed>"
        raise ValueError(
            f"project step {name!r} expected_result must be one of: succeeded, failed, blocked, running"
        )
    return value


def _load_contract_input(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if path.is_dir() or _looks_like_split_contract(path):
        bundle = load_contract_bundle(_bundle_base(path))
        environment = bundle.environment if isinstance(bundle.environment, dict) else None
        return bundle.contract, environment
    return _load_mapping(path, label="contract"), None


def _looks_like_split_contract(path: Path) -> bool:
    return any(
        marker in path.name
        for marker in (".ingestion.", ".annotations.", ".operations.", ".access.", ".environment.")
    )


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


def _load_mapping(path: Path, *, label: str) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} file must contain a YAML or JSON object")
    return loaded


__all__ = [
    "FabricProjectSetupResult",
    "FabricProjectSmokeResult",
    "FabricProjectSmokeStepResult",
    "run_fabric_project_smoke",
]
