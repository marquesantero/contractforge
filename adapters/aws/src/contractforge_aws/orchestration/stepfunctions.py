"""Render AWS Step Functions project orchestration artifacts."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from contractforge_aws.orchestration.project_graph import dependency_waves, state_key

_GLUE_START_SYNC = "arn:aws:states:::glue:startJobRun.sync"
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")


def render_stepfunctions_state_machine_definition(
    project: Mapping[str, Any],
    jobs: Mapping[str, str],
) -> dict[str, Any]:
    """Render an ASL state machine definition for a ContractForge project."""

    states: dict[str, Any] = {}
    waves = dependency_waves(_execution_steps(project))
    wave_names = [_wave_key(index) for index, _ in enumerate(waves, start=1)]
    for index, wave in enumerate(waves):
        state_name = wave_names[index]
        next_state = wave_names[index + 1] if index + 1 < len(wave_names) else None
        states[state_name] = _wave_state(wave, jobs, state_name, next_state)
    return {
        "Comment": f"ContractForge AWS project orchestration for {_project_name(project)}",
        "StartAt": wave_names[0],
        "States": states,
    }


def render_stepfunctions_state_machine_payload(
    project: Mapping[str, Any],
    jobs: Mapping[str, str],
    *,
    role_arn: str | None = None,
    state_machine_name: str | None = None,
    state_machine_type: str | None = None,
) -> dict[str, Any]:
    """Render the create/update payload used for a Step Functions state machine."""

    definition = render_stepfunctions_state_machine_definition(project, jobs)
    return {
        "name": state_machine_name or _state_machine_name(project),
        "roleArn": role_arn or "${STEP_FUNCTIONS_ROLE_ARN}",
        "type": state_machine_type or "STANDARD",
        "definition": json.dumps(definition, indent=2, sort_keys=True),
    }


def _wave_state(
    wave: Sequence[Mapping[str, Any]],
    jobs: Mapping[str, str],
    state_name: str,
    next_state: str | None,
) -> dict[str, Any]:
    builders = {
        True: lambda: _parallel_wave(wave, jobs),
        False: lambda: _task_state(wave[0], jobs),
    }
    state = builders[len(wave) > 1]()
    if state.get("Type") == "Parallel":
        state["ResultPath"] = f"$.{state_key(state_name)}"
    state["Next" if next_state else "End"] = next_state or True
    return state


def _parallel_wave(wave: Sequence[Mapping[str, Any]], jobs: Mapping[str, str]) -> dict[str, Any]:
    return {
        "Type": "Parallel",
        "Branches": [_parallel_branch(step, jobs) for step in wave],
    }


def _parallel_branch(step: Mapping[str, Any], jobs: Mapping[str, str]) -> dict[str, Any]:
    key = state_key(_step_name(step))
    return {
        "StartAt": key,
        "States": {
            key: {
                **_task_state(step, jobs),
                "End": True,
            }
        },
    }


def _task_state(step: Mapping[str, Any], jobs: Mapping[str, str]) -> dict[str, Any]:
    return {
        "Type": "Task",
        "Resource": _GLUE_START_SYNC,
        "Parameters": {
            "JobName": _job_name(step, jobs),
            "Arguments": {
                "--CONTRACTFORGE_MASTER_JOB_ID.$": "$$.StateMachine.Id",
                "--CONTRACTFORGE_MASTER_RUN_ID.$": "$$.Execution.Id",
                "--CONTRACTFORGE_PARENT_RUN_ID.$": "$$.Execution.Id",
                "--CONTRACTFORGE_RUN_GROUP_ID.$": "$$.Execution.Id",
            },
        },
        "ResultPath": f"$.{state_key(_step_name(step))}",
    }


def _job_name(step: Mapping[str, Any], jobs: Mapping[str, str]) -> str:
    name = _step_name(step)
    job_name = str(jobs.get(name) or "").strip()
    if not job_name:
        raise ValueError(f"AWS orchestration requires a Glue job name for project step {name!r}")
    return job_name


def _execution_steps(project: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    steps = project.get("execution_order")
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)) or not steps:
        raise ValueError("project.execution_order must be a non-empty list")
    if not all(isinstance(step, Mapping) for step in steps):
        raise ValueError("project.execution_order entries must be objects")
    return steps


def _project_name(project: Mapping[str, Any]) -> str:
    return str(project.get("name") or "contractforge_project")


def _state_machine_name(project: Mapping[str, Any]) -> str:
    deployment = _aws_deployment(project)
    name = str(deployment.get("state_machine_name") or _project_name(project)).strip()
    return _SAFE_NAME_RE.sub("-", name).strip("-") or "contractforge-project"


def _step_name(step: Mapping[str, Any]) -> str:
    return str(step.get("name") or "").strip()


def _wave_key(index: int) -> str:
    return f"Wave{index}"


def _aws_deployment(project: Mapping[str, Any]) -> Mapping[str, Any]:
    deployment = project.get("deployment")
    return deployment.get("aws", {}) if isinstance(deployment, Mapping) and isinstance(deployment.get("aws"), Mapping) else {}
