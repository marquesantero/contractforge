"""AWS project orchestration CLI helpers."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Sequence

from contractforge_core.project import adapter_scheduling
from contractforge_aws.orchestration import (
    render_eventbridge_scheduler_payload,
    render_stepfunctions_state_machine_definition,
    render_stepfunctions_state_machine_payload,
)
from contractforge_aws.orchestration.execution_name import execution_name
from contractforge_aws.runtime.orchestration import (
    create_or_update_schedule_payload,
    create_or_update_state_machine_payload,
    start_state_machine_execution,
    wait_state_machine_execution,
)


def project_orchestration_payload(
    project: Mapping[str, Any],
    steps: Sequence[Mapping[str, Any]],
    environment: Mapping[str, Any] | None,
    *,
    deploy: bool,
    run: bool = False,
    wait: bool = False,
    poll_interval_seconds: float = 30.0,
    max_wait_seconds: float = 3600.0,
) -> dict[str, Any]:
    jobs = _step_jobs(steps)
    settings = _settings(project, environment)
    _validate_deploy_settings(project, settings, deploy=deploy, run=run or wait)
    state_machine_payload = render_stepfunctions_state_machine_payload(
        project,
        jobs,
        role_arn=settings.get("state_machine_role_arn"),
        state_machine_name=settings.get("state_machine_name"),
        state_machine_type=settings.get("state_machine_type"),
    )
    definition = render_stepfunctions_state_machine_definition(project, jobs)
    payload: dict[str, Any] = {
        "type": "stepfunctions",
        "jobs": jobs,
        "state_machine": {
            "name": state_machine_payload["name"],
            "type": state_machine_payload["type"],
            "definition": definition,
        },
    }
    deployment = _deployment_result(state_machine_payload, settings, deploy)
    state_machine_arn = deployment.get("arn") or settings.get("state_machine_arn")
    schedule = render_eventbridge_scheduler_payload(
        project,
        state_machine_arn=state_machine_arn,
        role_arn=settings.get("scheduler_role_arn"),
    )
    payload.update(_optional_schedule_payload(schedule, deploy=deploy))
    payload.update({"deployment": deployment} if deployment else {})
    payload.update(
        _execution_payload(
            project,
            settings,
            deployment,
            run=run or wait,
            wait=wait,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
        )
    )
    return payload


def _deployment_result(payload: dict[str, Any], settings: Mapping[str, str], deploy: bool) -> dict[str, Any]:
    if not deploy:
        return {}
    result = create_or_update_state_machine_payload(
        payload,
        state_machine_arn=settings.get("state_machine_arn"),
    )
    return asdict(result)


def _optional_schedule_payload(schedule: dict[str, Any] | None, *, deploy: bool) -> dict[str, Any]:
    if not schedule:
        return {}
    payload: dict[str, Any] = {"schedule": schedule}
    if deploy:
        payload["schedule_deployment"] = asdict(create_or_update_schedule_payload(schedule))
    return payload


def _execution_payload(
    project: Mapping[str, Any],
    settings: Mapping[str, str],
    deployment: Mapping[str, Any],
    *,
    run: bool,
    wait: bool,
    poll_interval_seconds: float,
    max_wait_seconds: float,
) -> dict[str, Any]:
    if not run:
        return {}
    state_machine_arn = str(deployment.get("arn") or settings.get("state_machine_arn") or "").strip()
    execution = start_state_machine_execution(
        state_machine_arn=state_machine_arn,
        name=execution_name(project, settings),
    )
    payload: dict[str, Any] = {"execution": asdict(execution)}
    if wait:
        payload["wait"] = asdict(
            wait_state_machine_execution(
                execution_arn=execution.execution_arn,
                poll_interval_seconds=poll_interval_seconds,
                max_wait_seconds=max_wait_seconds,
            )
        )
    return payload


def _validate_deploy_settings(
    project: Mapping[str, Any],
    settings: Mapping[str, str],
    *,
    deploy: bool,
    run: bool,
) -> None:
    validators = (
        (deploy, "state_machine_role_arn", "parameters.aws.step_functions.role_arn is required for --deploy-orchestration"),
        (
            run and not deploy,
            "state_machine_arn",
            "deployment.aws.state_machine_arn or parameters.aws.step_functions.state_machine_arn is required for --run-orchestration without --deploy-orchestration",
        ),
        (
            deploy and bool(_aws_schedule(project)),
            "scheduler_role_arn",
            "parameters.aws.scheduler.role_arn is required to deploy scheduling.aws.schedule",
        ),
    )
    missing = [message for enabled, key, message in validators if enabled and not settings.get(key)]
    if missing:
        raise ValueError("; ".join(missing))


def _step_jobs(steps: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    jobs = {_step_name(step): _job_name(step) for step in steps}
    missing = [name for name, job in jobs.items() if not job]
    if missing:
        raise ValueError(f"AWS orchestration requires Glue job names for project steps: {', '.join(missing)}")
    return jobs


def _job_name(step: Mapping[str, Any]) -> str:
    deployment = step.get("deployment")
    return str((deployment or {}).get("job_name") or step.get("job_name") or "").strip()


def _step_name(step: Mapping[str, Any]) -> str:
    return str(step.get("name") or "").strip()


def _settings(project: Mapping[str, Any], environment: Mapping[str, Any] | None) -> dict[str, str]:
    aws = _aws_deployment(project)
    params = _aws_parameters(environment)
    step_functions = _mapping(params.get("step_functions"))
    scheduler = _mapping(params.get("scheduler"))
    keys = {
        "state_machine_name": (aws, step_functions, "state_machine_name"),
        "state_machine_arn": (aws, step_functions, "state_machine_arn"),
        "state_machine_role_arn": (aws, step_functions, "role_arn"),
        "state_machine_type": (aws, step_functions, "type"),
        "scheduler_role_arn": (aws, scheduler, "role_arn"),
    }
    return {name: _first_text(*sources) for name, sources in keys.items() if _first_text(*sources)}


def _first_text(primary: Mapping[str, Any], secondary: Mapping[str, Any], key: str) -> str:
    for source in (primary, secondary):
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _aws_deployment(project: Mapping[str, Any]) -> Mapping[str, Any]:
    deployment = project.get("deployment")
    aws = deployment.get("aws") if isinstance(deployment, Mapping) else None
    return aws if isinstance(aws, Mapping) else {}


def _aws_schedule(project: Mapping[str, Any]) -> Mapping[str, Any]:
    schedule = adapter_scheduling(project, "aws").get("schedule")
    return schedule if isinstance(schedule, Mapping) else {}


def _aws_parameters(environment: Mapping[str, Any] | None) -> Mapping[str, Any]:
    parameters = environment.get("parameters") if isinstance(environment, Mapping) else None
    aws = parameters.get("aws") if isinstance(parameters, Mapping) else None
    return aws if isinstance(aws, Mapping) else {}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
