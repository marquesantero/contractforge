"""Glue job payload normalization for optional runtime registration."""

from __future__ import annotations

import json
from typing import Any

from contractforge_aws.glue_job_definition import validate_glue_job_arguments
from contractforge_aws.validation import required_text


def coerce_glue_job_payload(payload: dict[str, Any] | str) -> tuple[str, dict[str, Any]]:
    mapping = _payload_mapping(payload)
    name = required_text(mapping.get("Name"), "Glue job payload Name")
    return name, _job_payload(mapping)


def _payload_mapping(payload: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(payload, str):
        loaded = json.loads(payload)
        if not isinstance(loaded, dict):
            raise ValueError("Glue job payload JSON must decode to an object")
        return loaded
    return payload


def _job_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Glue job payload must be a mapping")
    values = {key: payload[key] for key in _GLUE_JOB_PAYLOAD_KEYS if key in payload}
    required_text(values.get("Role"), "Glue job payload Role")
    command = values.get("Command")
    if not isinstance(command, dict):
        raise ValueError("Glue job payload Command must be a mapping")
    script_location = required_text(command.get("ScriptLocation"), "Glue job payload Command.ScriptLocation")
    if not script_location.startswith("s3://"):
        raise ValueError("Glue job payload Command.ScriptLocation must start with s3://")
    arguments = values.get("DefaultArguments")
    if arguments is not None:
        values["DefaultArguments"] = validate_glue_job_arguments(arguments)
    return values


_GLUE_JOB_PAYLOAD_KEYS = {
    "Role",
    "Description",
    "Command",
    "DefaultArguments",
    "GlueVersion",
    "WorkerType",
    "NumberOfWorkers",
    "Timeout",
    "MaxRetries",
    "Connections",
    "ExecutionProperty",
    "NotificationProperty",
    "SecurityConfiguration",
    "Tags",
}
