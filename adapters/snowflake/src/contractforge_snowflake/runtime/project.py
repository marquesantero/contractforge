"""Project-level Snowflake publish/deployment helpers."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from contractforge_core.contracts import load_contract_bundle
from contractforge_core.project import project_schedule_intent
from contractforge_snowflake.connection_options import validate_connect_options
from contractforge_snowflake.deployment.procedure import render_runtime_procedure_sql
from contractforge_snowflake.deployment.task_graph import (
    DEFAULT_RUNNER_PROCEDURE,
    DEFAULT_TASK_DATABASE,
    DEFAULT_TASK_SCHEMA,
    SnowflakeTaskGraphStep,
    artifact_uri,
    render_project_task_graph,
    render_task_graph_run_sql,
    render_task_history_query,
)
from contractforge_snowflake.api import build_snowflake_publish_bundle, plan_snowflake_contract
from contractforge_snowflake.polling import clamped_poll_interval
from contractforge_snowflake.runtime.publish import SnowflakeStagePublishResult, publish_snowflake_contract
from contractforge_snowflake.naming import quote_identifier, quote_multipart_identifier

ConnectionFactory = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class SnowflakeProjectStepResult:
    name: str
    contract: str
    expected_result: str
    planning_status: str
    warning_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    artifact_count: int
    artifacts: tuple[str, ...] = ()
    runtime_contract_uri: str | None = None
    runtime_environment_uri: str | None = None
    depends_on: tuple[str, ...] = ()
    deployment: SnowflakeStagePublishResult | None = None


@dataclass(frozen=True)
class SnowflakeProjectDeployment:
    project: str
    environment: str | None
    environment_key: str
    dry_run: bool
    execution_model: str
    steps: tuple[SnowflakeProjectStepResult, ...]
    deployment_artifacts: dict[str, str]
    applied_deployment_commands: tuple[str, ...] = ()

    def to_dict(self, *, summary_only: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if summary_only:
            for step in payload["steps"]:
                step.pop("artifacts", None)
                deployment = step.get("deployment")
                if isinstance(deployment, dict):
                    deployment["artifact_count"] = len(deployment.get("artifacts") or ())
                    deployment.pop("artifacts", None)
        return payload


@dataclass(frozen=True)
class SnowflakeProjectRunResult:
    project: str
    environment: str | None
    environment_key: str
    dry_run: bool
    task_names: tuple[str, ...]
    root_tasks: tuple[str, ...]
    commands: tuple[str, ...]
    wait: dict[str, Any] | None = None


@dataclass(frozen=True)
class SnowflakeProjectCleanupPlan:
    project: str
    environment: str | None
    environment_key: str
    dry_run: bool
    commands: tuple[str, ...]
    notes: tuple[str, ...]


def deploy_snowflake_project(
    project: str | Path,
    *,
    environment: str | Path | None = None,
    environment_key: str = "snowflake",
    stage: str | None = None,
    prefix: str | None = None,
    dry_run: bool = False,
    summary_only: bool = False,
    connection: Any | None = None,
    connect_options: dict[str, Any] | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> SnowflakeProjectDeployment:
    """Publish every Snowflake contract declared by a ContractForge project."""

    project_file = _project_file(project)
    project_root = project_file.parent
    project_payload = _load_mapping(project_file, label="project")
    environment_path = Path(environment) if environment else _project_environment_path(project_payload, project_root, environment_key)
    environment_payload = _load_mapping(environment_path, label="environment") if environment_path else None
    steps = tuple(
        _deploy_project_step(
            step,
            project_root=project_root,
            environment=environment_payload,
            environment_key=environment_key,
            stage=stage,
            prefix=prefix,
            dry_run=dry_run,
            summary_only=summary_only,
            connection=connection,
            connect_options=connect_options,
            connection_factory=connection_factory,
        )
        for step in _project_execution_steps(project_payload)
    )
    deployment_artifacts = _project_deployment_artifacts(
        project_payload,
        environment=environment_payload,
        steps=steps,
        stage=stage,
        prefix=prefix,
    )
    applied_deployment_commands = (
        ()
        if dry_run or not deployment_artifacts
        else _apply_project_deployment_artifacts(
            deployment_artifacts,
            connection=connection,
            connect_options=connect_options,
            connection_factory=connection_factory,
        )
    )
    return SnowflakeProjectDeployment(
        project=str(project_file),
        environment=str(environment_path) if environment_path else None,
        environment_key=environment_key,
        dry_run=dry_run,
        execution_model="library_runner",
        steps=steps,
        deployment_artifacts=deployment_artifacts,
        applied_deployment_commands=applied_deployment_commands,
    )


def run_snowflake_project(
    project: str | Path,
    *,
    environment: str | Path | None = None,
    environment_key: str = "snowflake",
    dry_run: bool = False,
    wait: bool = False,
    poll_interval_seconds: float = 10.0,
    max_wait_seconds: float = 3600.0,
    connection: Any | None = None,
    connect_options: dict[str, Any] | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> SnowflakeProjectRunResult:
    """Execute the root tasks for an already deployed Snowflake project task graph."""

    project_file, project_payload, environment_path, environment_payload, steps = _project_context(
        project,
        environment=environment,
        environment_key=environment_key,
    )
    if not _needs_project_task_graph(project_payload, steps):
        raise ValueError("Snowflake run-project requires a scheduled or dependency task graph")
    task_names = tuple(step.name for step in steps)
    root_tasks = tuple(step.name for step in steps if not step.depends_on)
    dependent_tasks = tuple(step.name for step in steps if step.depends_on)
    if not root_tasks:
        raise ValueError("Snowflake run-project could not determine root tasks")
    commands = _split_sql_script(
        render_task_graph_run_sql(
            environment=environment_payload,
            root_task_names=root_tasks,
            dependent_task_names=dependent_tasks,
        )
    )
    wait_payload = None
    if not dry_run:
        owner = _ConnectionOwner(connection=connection, connect_options=connect_options, connection_factory=connection_factory)
        try:
            started_after = datetime.now(timezone.utc)
            for command in commands:
                _execute_one(owner.connection, command)
            if wait:
                wait_payload = wait_snowflake_project_tasks(
                    connection=owner.connection,
                    environment=environment_payload,
                    task_names=task_names,
                    poll_interval_seconds=poll_interval_seconds,
                    max_wait_seconds=max_wait_seconds,
                    started_after=started_after,
                )
        finally:
            owner.close()
    return SnowflakeProjectRunResult(
        project=str(project_file),
        environment=str(environment_path) if environment_path else None,
        environment_key=environment_key,
        dry_run=dry_run,
        task_names=task_names,
        root_tasks=root_tasks,
        commands=commands,
        wait=wait_payload,
    )


def wait_snowflake_project_tasks(
    *,
    connection: Any,
    environment: dict[str, Any] | None,
    task_names: tuple[str, ...],
    poll_interval_seconds: float = 10.0,
    max_wait_seconds: float = 3600.0,
    started_after: Any | None = None,
) -> dict[str, Any]:
    """Poll Snowflake task history until all named tasks have a terminal row."""

    deadline = time.monotonic() + max_wait_seconds
    poll_interval = clamped_poll_interval(poll_interval_seconds)
    terminal_states = {"SUCCEEDED", "FAILED", "CANCELLED", "SKIPPED"}
    history_query = render_task_history_query(environment=environment, task_names=task_names, limit=100)
    task_name_set = {task.lower() for task in task_names}
    while True:
        latest: dict[str, dict[str, Any]] = {}
        rows = _fetch_rows(connection, history_query)
        for row in rows:
            name = str(_row_value(row, 0, "NAME")).lower()
            state = str(_row_value(row, 1, "STATE") or "").upper()
            query_id = _row_value(row, 2, "QUERY_ID")
            scheduled_time = _row_value(row, 3, "SCHEDULED_TIME")
            if started_after is not None and not _at_or_after(scheduled_time, started_after):
                continue
            if state == "SCHEDULED" and query_id is None:
                continue
            if name in task_name_set and name not in latest:
                latest[name] = {"name": name, "state": state, "query_id": query_id}
        if all(task.lower() in latest and latest[task.lower()]["state"] in terminal_states for task in task_names):
            status = "SUCCESS" if all(item["state"] == "SUCCEEDED" for item in latest.values()) else "FAILED"
            return {"status": status, "tasks": tuple(latest[task.lower()] for task in task_names), "query": history_query}
        failures = tuple(item for item in latest.values() if item["state"] in {"FAILED", "CANCELLED", "SKIPPED"})
        if failures:
            return {"status": "FAILED", "tasks": failures, "query": history_query}
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Snowflake task graph did not finish within {max_wait_seconds} seconds")
        time.sleep(poll_interval)


def build_snowflake_project_cleanup_plan(
    project: str | Path,
    *,
    environment: str | Path | None = None,
    environment_key: str = "snowflake",
) -> SnowflakeProjectCleanupPlan:
    """Render an explicit non-destructive cleanup plan for Snowflake project deployment artifacts."""

    project_file, _project_payload, environment_path, environment_payload, steps = _project_context(
        project,
        environment=environment,
        environment_key=environment_key,
    )
    snowflake = _snowflake_parameters(environment_payload)
    task_database = str(snowflake.get("task_database") or DEFAULT_TASK_DATABASE)
    task_schema = str(snowflake.get("task_schema") or DEFAULT_TASK_SCHEMA)
    procedure = str(snowflake.get("runner_procedure") or DEFAULT_RUNNER_PROCEDURE)
    commands = tuple(
        f"DROP TASK IF EXISTS {_task_identifier(task_database, task_schema, step.name)}"
        for step in reversed(steps)
    ) + (f"DROP PROCEDURE IF EXISTS {quote_multipart_identifier(procedure)}(STRING, STRING)",)
    notes = (
        "Cleanup plan is not executed by this command.",
        "Data target tables and staged artifacts are intentionally not dropped.",
    )
    return SnowflakeProjectCleanupPlan(
        project=str(project_file),
        environment=str(environment_path) if environment_path else None,
        environment_key=environment_key,
        dry_run=True,
        commands=commands,
        notes=notes,
    )


def _deploy_project_step(
    step: dict[str, Any],
    *,
    project_root: Path,
    environment: dict[str, Any] | None,
    environment_key: str,
    stage: str | None,
    prefix: str | None,
    dry_run: bool,
    summary_only: bool,
    connection: Any | None,
    connect_options: dict[str, Any] | None,
    connection_factory: ConnectionFactory | None,
) -> SnowflakeProjectStepResult:
    contract_ref = _step_contract_path(step, environment_key)
    contract_path = project_root / contract_ref
    contract, bundle_environment = _load_contract_input(contract_path)
    effective_environment = environment or bundle_environment
    planning = plan_snowflake_contract(contract, environment=effective_environment)
    bundle = build_snowflake_publish_bundle(contract, environment=effective_environment)
    deployment = None
    if not dry_run:
        deployment = publish_snowflake_contract(
            contract,
            environment=effective_environment,
            stage=stage,
            prefix=prefix,
            connection=connection,
            connect_options=connect_options,
            connection_factory=connection_factory,
        )
    artifacts = () if summary_only else tuple(sorted(bundle.artifacts))
    artifact_names = tuple(sorted(bundle.artifacts))
    return SnowflakeProjectStepResult(
        name=str(step.get("name") or contract_path.stem),
        contract=str(contract_path),
        expected_result=str(step.get("expected_result") or "succeeded"),
        planning_status=planning.status,
        warning_codes=tuple(warning.code for warning in planning.warnings),
        blocker_codes=tuple(blocker.code for blocker in planning.blockers),
        artifact_count=len(bundle.artifacts),
        artifacts=artifacts,
        runtime_contract_uri=_runtime_artifact_uri(artifact_names, suffix=".contract.json", environment=effective_environment, stage=stage, prefix=prefix),
        runtime_environment_uri=_runtime_artifact_uri(artifact_names, suffix=".environment.json", environment=effective_environment, stage=stage, prefix=prefix),
        depends_on=_step_dependencies(step),
        deployment=deployment,
    )


def _project_deployment_artifacts(
    project: dict[str, Any],
    *,
    environment: dict[str, Any] | None,
    steps: tuple[SnowflakeProjectStepResult, ...],
    stage: str | None,
    prefix: str | None,
) -> dict[str, str]:
    if not _needs_project_task_graph(project, steps):
        return {}
    graph_steps = tuple(
        SnowflakeTaskGraphStep(
            name=step.name,
            contract_artifact=_required_runtime_uri(step.runtime_contract_uri, step.name, "contract"),
            environment_artifact=step.runtime_environment_uri,
            depends_on=step.depends_on,
        )
        for step in steps
    )
    task_graph = render_project_task_graph(project, environment=environment, steps=graph_steps)
    return {
        "deployment/snowflake_runtime_procedure.sql": render_runtime_procedure_sql(environment),
        **({"deployment/snowflake_task_graph.sql": task_graph} if task_graph else {}),
    }


def _needs_project_task_graph(project: dict[str, Any], steps: tuple[SnowflakeProjectStepResult, ...]) -> bool:
    return project_schedule_intent(project) is not None or any(step.depends_on for step in steps)


def _runtime_artifact_uri(
    artifact_names: tuple[str, ...],
    *,
    suffix: str,
    environment: dict[str, Any] | None,
    stage: str | None,
    prefix: str | None,
) -> str | None:
    name = next((artifact for artifact in artifact_names if artifact.startswith("runtime/") and artifact.endswith(suffix)), None)
    if not name:
        return None
    return artifact_uri(artifact_name=name, artifact_root=_environment_artifact_uri(environment), stage=stage, prefix=prefix)


def _required_runtime_uri(value: str | None, step_name: str, artifact_type: str) -> str:
    if value:
        return value
    raise ValueError(
        f"Snowflake project step {step_name!r} requires an artifact destination to render task graph {artifact_type} URI"
    )


def _environment_artifact_uri(environment: dict[str, Any] | None) -> str | None:
    artifacts = environment.get("artifacts") if isinstance(environment, dict) else None
    return str(artifacts.get("uri")) if isinstance(artifacts, dict) and artifacts.get("uri") else None


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


def _project_file(project: str | Path) -> Path:
    path = Path(project)
    return path / "project.yaml" if path.is_dir() else path


def _project_context(
    project: str | Path,
    *,
    environment: str | Path | None,
    environment_key: str,
) -> tuple[Path, dict[str, Any], Path | None, dict[str, Any] | None, tuple[SnowflakeProjectStepResult, ...]]:
    project_file = _project_file(project)
    project_root = project_file.parent
    project_payload = _load_mapping(project_file, label="project")
    environment_path = Path(environment) if environment else _project_environment_path(project_payload, project_root, environment_key)
    environment_payload = _load_mapping(environment_path, label="environment") if environment_path else None
    steps = tuple(
        _deploy_project_step(
            step,
            project_root=project_root,
            environment=environment_payload,
            environment_key=environment_key,
            stage=None,
            prefix=None,
            dry_run=True,
            summary_only=True,
            connection=None,
            connect_options=None,
            connection_factory=None,
        )
        for step in _project_execution_steps(project_payload)
    )
    return project_file, project_payload, environment_path, environment_payload, steps


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


def _step_contract_path(step: dict[str, Any], environment_key: str) -> str:
    contracts = step.get("contracts")
    if not isinstance(contracts, dict) or environment_key not in contracts:
        name = step.get("name") or "<unnamed>"
        raise ValueError(f"project step {name!r} must declare contracts.{environment_key}")
    return str(contracts[environment_key])


def _load_contract_input(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if path.is_dir() or _looks_like_split_contract(path) or _has_project_context(path):
        bundle = load_contract_bundle(_bundle_base(path))
        environment = bundle.environment if isinstance(bundle.environment, dict) else None
        return bundle.contract, environment
    return _load_mapping(path, label="contract"), None


def _looks_like_split_contract(path: Path) -> bool:
    return any(marker in path.name for marker in (".ingestion.", ".annotations.", ".operations.", ".access.", ".environment."))


def _has_project_context(path: Path) -> bool:
    base = path if path.is_dir() else path.parent
    return any((candidate / "project.yaml").exists() or (candidate / "project.yml").exists() for candidate in (base, *base.parents))


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


def project_deployment_json(deployment: SnowflakeProjectDeployment, *, summary_only: bool = False) -> str:
    return json.dumps(deployment.to_dict(summary_only=summary_only), indent=2, sort_keys=True, default=str)


def _apply_project_deployment_artifacts(
    artifacts: dict[str, str],
    *,
    connection: Any | None,
    connect_options: dict[str, Any] | None,
    connection_factory: ConnectionFactory | None,
) -> tuple[str, ...]:
    owner = _ConnectionOwner(connection=connection, connect_options=connect_options, connection_factory=connection_factory)
    try:
        commands: list[str] = []
        for name in sorted(artifacts):
            commands.extend(_execute_sql_script(owner.connection, artifacts[name]))
        return tuple(commands)
    finally:
        owner.close()


class _ConnectionOwner:
    def __init__(
        self,
        *,
        connection: Any | None,
        connect_options: dict[str, Any] | None,
        connection_factory: ConnectionFactory | None,
    ) -> None:
        self._owns_connection = connection is None
        self.connection = connection or _connect_with_factory(connect_options or {}, connection_factory=connection_factory)

    def close(self) -> None:
        if self._owns_connection and hasattr(self.connection, "close"):
            self.connection.close()


def _execute_sql_script(connection: Any, script: str) -> tuple[str, ...]:
    commands = _split_sql_script(script)
    cursor = connection.cursor()
    try:
        for command in commands:
            cursor.execute(command)
    finally:
        if hasattr(cursor, "close"):
            cursor.close()
    return commands


def _execute_one(connection: Any, command: str) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(command)
    finally:
        if hasattr(cursor, "close"):
            cursor.close()


def _fetch_rows(connection: Any, command: str) -> list[Any]:
    cursor = connection.cursor()
    try:
        cursor.execute(command)
        return list(cursor.fetchall()) if getattr(cursor, "description", None) else []
    finally:
        if hasattr(cursor, "close"):
            cursor.close()


def _split_sql_script(script: str) -> tuple[str, ...]:
    return tuple(statement.strip() for statement in script.split(";") if statement.strip())


def _snowflake_parameters(environment: dict[str, Any] | None) -> dict[str, Any]:
    parameters = environment.get("parameters") if isinstance(environment, dict) else None
    snowflake = parameters.get("snowflake") if isinstance(parameters, dict) else None
    return dict(snowflake) if isinstance(snowflake, dict) else {}


def _task_identifier(database: str, schema: str, name: str) -> str:
    return ".".join((quote_identifier(database), quote_identifier(schema), quote_identifier(name)))


def _row_value(row: Any, index: int, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[index]
    except (TypeError, KeyError, IndexError):
        return getattr(row, key, None)


def _at_or_after(value: Any, lower_bound: Any) -> bool:
    if value is None:
        return False
    try:
        return value >= lower_bound
    except TypeError:
        return str(value) >= str(lower_bound)


def _connect_with_factory(options: dict[str, Any], *, connection_factory: ConnectionFactory | None) -> Any:
    connect_options = validate_connect_options(options)
    if connection_factory is not None:
        return connection_factory(connect_options)
    return _connect(connect_options)


def _connect(options: dict[str, Any]) -> Any:
    connect_options = validate_connect_options(options)
    try:
        import snowflake.connector
    except ImportError as exc:  # pragma: no cover - runtime extra path
        raise RuntimeError(
            "Deploying Snowflake project tasks requires the runtime extra: pip install contractforge-snowflake[runtime]"
        ) from exc
    return snowflake.connector.connect(**connect_options)


__all__ = [
    "SnowflakeProjectCleanupPlan",
    "SnowflakeProjectDeployment",
    "SnowflakeProjectRunResult",
    "SnowflakeProjectStepResult",
    "build_snowflake_project_cleanup_plan",
    "deploy_snowflake_project",
    "project_deployment_json",
    "run_snowflake_project",
    "wait_snowflake_project_tasks",
]
