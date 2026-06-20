"""Render deterministic AWS Glue deployment review artifacts."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.connectors import is_available_now_stream_source, is_bounded_stream_source, is_delta_share_source
from contractforge_core.semantic import SemanticContract
from contractforge_aws.contract_extensions import aws_extensions
from contractforge_aws.glue_job_definition import (
    CONTRACTFORGE_GLUE_ARGUMENTS,
    GlueJobDefinition,
    build_glue_job_payload,
)
from contractforge_aws.rendering.names import artifact_prefix
from contractforge_aws.runtime_args import CONTRACT_URI_ARG, ENVIRONMENT_URI_ARG, RUNTIME_MODE_ARG
from contractforge_aws.sources import is_incremental_file_source, jdbc_uses_bookmarks, source_requires_rest_helper
from contractforge_aws.sources.classification import source_requires_runtime_file_config


def render_glue_job_definition(
    contract: SemanticContract,
    *,
    environment_parameters: dict[str, Any] | None = None,
) -> str:
    """Render the Glue create/update payload without calling AWS APIs."""

    return json.dumps(
        glue_job_definition_payload(contract, environment_parameters=environment_parameters),
        indent=2,
        sort_keys=True,
    ) + "\n"


def glue_job_definition_payload(
    contract: SemanticContract,
    *,
    environment_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = _definition(contract, environment_parameters=environment_parameters)
    return {
        "Name": definition.name,
        **build_glue_job_payload(definition),
        "contractforge_review_notes": _review_notes(contract),
    }


def _definition(
    contract: SemanticContract,
    *,
    environment_parameters: dict[str, Any] | None = None,
) -> GlueJobDefinition:
    glue_job = _merged_adapter_map("glue_job", contract, environment_parameters)
    _validate_library_runner_mode(glue_job)
    job_name = _text(glue_job, "name", f"contractforge_{artifact_prefix(contract)}")
    return GlueJobDefinition(
        name=job_name,
        role_arn=_text(glue_job, "role_arn", "${glue_role_arn}"),
        script_s3_uri=_text(
            glue_job,
            "script_s3_uri",
            "s3://${artifact_bucket}/${artifact_prefix}/runtime/contractforge_aws_runner.py",
        ),
        glue_version=_text(glue_job, "glue_version", "4.0"),
        worker_type=_text(glue_job, "worker_type", "G.1X"),
        number_of_workers=_int(glue_job, "number_of_workers", 2),
        timeout_minutes=_int(glue_job, "timeout_minutes", 60),
        max_retries=_int(glue_job, "max_retries", 0),
        enable_job_bookmark=_bookmark_enabled(contract, glue_job, environment_parameters),
        default_arguments=_default_arguments(contract, glue_job, environment_parameters),
        spark_conf=_string_map(glue_job.get("spark_conf")),
        connection_names=_connection_names(glue_job),
        description=_text(glue_job, "description", "ContractForge AWS Glue Iceberg ingestion job."),
    )

def _bookmark_enabled(
    contract: SemanticContract,
    glue_job: dict[str, Any],
    environment_parameters: dict[str, Any] | None,
) -> bool:
    bookmarks = _merged_adapter_map("job_bookmarks", contract, environment_parameters)
    value = _first_present(glue_job, bookmarks, "enable_job_bookmark", "enabled")
    source = contract.source.raw or {}
    return bool(value) if value is not None else is_incremental_file_source(source) or jdbc_uses_bookmarks(source)


def _default_arguments(
    contract: SemanticContract,
    glue_job: dict[str, Any],
    environment_parameters: dict[str, Any] | None,
) -> dict[str, str]:
    arguments = _dependency_arguments(contract, environment_parameters)
    prefix = artifact_prefix(contract)
    arguments.update(
        {
            f"--{RUNTIME_MODE_ARG}": "library_runner",
            f"--{CONTRACT_URI_ARG}": f"s3://${{artifact_bucket}}/${{artifact_prefix}}/runtime/{prefix}.contract.json",
        }
    )
    if environment_parameters is not None:
        arguments[f"--{ENVIRONMENT_URI_ARG}"] = (
            f"s3://${{artifact_bucket}}/${{artifact_prefix}}/runtime/{prefix}.environment.json"
        )
    declared = _string_map(glue_job.get("default_arguments"))
    reserved = CONTRACTFORGE_GLUE_ARGUMENTS | set(arguments)
    overlap = sorted(set(declared) & reserved)
    if overlap:
        joined = ", ".join(overlap)
        raise ValueError(
            "extensions.aws.glue_job.default_arguments cannot override adapter-owned Glue arguments: "
            f"{joined}"
        )
    return {**arguments, **declared}


def _dependency_arguments(contract: SemanticContract, environment_parameters: dict[str, Any] | None) -> dict[str, str]:
    dependencies = _merged_adapter_map("dependencies", contract, environment_parameters)
    modules = _dependency_value(dependencies, "additional_python_modules", "python_modules")
    if not modules and source_requires_rest_helper(contract.source.raw or {}):
        modules = "contractforge-core"
    values = {
        "--additional-python-modules": modules,
        "--extra-jars": _dependency_value(dependencies, "extra_jars", "jars"),
        "--extra-py-files": _dependency_value(dependencies, "extra_py_files", "py_files"),
    }
    return {key: value for key, value in values.items() if value}


def _review_notes(contract: SemanticContract) -> list[str]:
    source = contract.source.raw or {}
    notes = [
        "This is a deterministic deployment artifact; rendering does not call AWS.",
        "Replace placeholder role/script values before registering the job.",
        "Review IAM, Lake Formation, networking and artifact bucket boundaries before applying.",
    ]
    if source_requires_runtime_file_config(source):
        notes.append(
            "This source requires reviewed Glue runtime connector/package and credential configuration before execution."
        )
    if is_bounded_stream_source(source) or is_available_now_stream_source(source) or is_delta_share_source(source):
        notes.append(
            "This source requires the matching Spark connector jar/package through extensions.aws.dependencies before execution."
        )
    return notes


def _dependency_value(dependencies: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = dependencies.get(key)
        if isinstance(value, (list, tuple)):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _validate_library_runner_mode(glue_job: dict[str, Any]) -> None:
    value = glue_job.get("runtime_mode")
    if value is None or str(value).strip() in {"", "library_runner"}:
        return
    raise ValueError(
        "extensions.aws.glue_job.runtime_mode no longer supports generated_script; "
        "AWS Glue deployments always use the ContractForge library runner."
    )


def _map_extension(name: str, contract: SemanticContract) -> dict[str, Any]:
    value = aws_extensions(contract).get(name)
    return dict(value) if isinstance(value, dict) else {}


def _map_environment(name: str, environment_parameters: dict[str, Any] | None) -> dict[str, Any]:
    value = (environment_parameters or {}).get(name)
    return dict(value) if isinstance(value, dict) else {}


def _merged_adapter_map(
    name: str,
    contract: SemanticContract,
    environment_parameters: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = _map_environment(name, environment_parameters)
    merged.update(_map_extension(name, contract))
    return merged


def _text(values: dict[str, Any], key: str, default: str) -> str:
    value = values.get(key)
    return str(value).strip() if value is not None and str(value).strip() else default


def _int(values: dict[str, Any], key: str, default: int) -> int:
    value = values.get(key)
    return default if value is None or value == "" else int(value)


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _connection_names(glue_job: dict[str, Any]) -> tuple[str, ...]:
    raw = glue_job.get("connection_names") or glue_job.get("connections") or ()
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        values = []
    return tuple(str(value).strip() for value in values if str(value).strip())


def _first_present(primary: dict[str, Any], secondary: dict[str, Any], *keys: str) -> Any:
    for mapping in (primary, secondary):
        for key in keys:
            if key in mapping:
                return mapping[key]
    return None
