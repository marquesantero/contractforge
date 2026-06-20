"""SDK-free AWS Glue job definition models."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from contractforge_aws.validation import required_text

CONTRACTFORGE_GLUE_ARGUMENTS = frozenset(
    {
        "--conf",
        "--datalake-formats",
        "--enable-glue-datacatalog",
        "--job-bookmark-option",
        "--job-language",
    }
)

ICEBERG_SPARK_CONF = {
    "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
}


@dataclass(frozen=True)
class GlueJobDefinition:
    name: str
    role_arn: str
    script_s3_uri: str
    glue_version: str = "4.0"
    worker_type: str = "G.1X"
    number_of_workers: int = 2
    timeout_minutes: int = 60
    max_retries: int = 0
    enable_job_bookmark: bool = False
    default_arguments: dict[str, str] | None = None
    spark_conf: dict[str, str] | None = None
    connection_names: tuple[str, ...] = ()
    description: str = "ContractForge AWS Glue Iceberg ingestion job."


def build_glue_job_payload(definition: GlueJobDefinition) -> dict[str, Any]:
    _validate_definition(definition)
    default_arguments = {
        "--conf": _render_spark_conf(definition.spark_conf),
        "--datalake-formats": "iceberg",
        "--enable-glue-datacatalog": "true",
        "--job-language": "python",
        "--job-bookmark-option": "job-bookmark-enable" if definition.enable_job_bookmark else "job-bookmark-disable",
    }
    default_arguments.update(
        validate_glue_job_arguments(
            definition.default_arguments or {},
            reserved_keys=CONTRACTFORGE_GLUE_ARGUMENTS,
        )
    )
    payload = {
        "Role": definition.role_arn,
        "Description": definition.description,
        "Command": {
            "Name": "glueetl",
            "ScriptLocation": definition.script_s3_uri,
            "PythonVersion": "3",
        },
        "DefaultArguments": default_arguments,
        "GlueVersion": definition.glue_version,
        "WorkerType": definition.worker_type,
        "NumberOfWorkers": definition.number_of_workers,
        "Timeout": definition.timeout_minutes,
        "MaxRetries": definition.max_retries,
    }
    if definition.connection_names:
        payload["Connections"] = {"Connections": list(definition.connection_names)}
    return payload


def validate_glue_job_arguments(
    arguments: dict[str, str],
    *,
    reserved_keys: Iterable[str] = (),
) -> dict[str, str]:
    if not isinstance(arguments, dict):
        raise ValueError("Glue job arguments must be a mapping")
    validated: dict[str, str] = {}
    reserved = set(reserved_keys)
    for key, value in arguments.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Glue job argument keys must be non-empty strings")
        if key in reserved:
            raise ValueError(f"Glue job argument {key!r} is managed by ContractForge and cannot be overridden")
        if not isinstance(value, str):
            raise ValueError("Glue job argument values must be strings")
        validated[key] = value
    return validated


def _validate_definition(definition: GlueJobDefinition) -> None:
    required_text(definition.name, "Glue job name")
    required_text(definition.role_arn, "Glue job role_arn")
    if not definition.script_s3_uri.startswith("s3://"):
        raise ValueError("Glue job script_s3_uri must start with s3://")
    if definition.number_of_workers < 1:
        raise ValueError("Glue job number_of_workers must be >= 1")
    if definition.timeout_minutes < 1:
        raise ValueError("Glue job timeout_minutes must be >= 1")
    validate_glue_job_arguments(definition.default_arguments or {}, reserved_keys=CONTRACTFORGE_GLUE_ARGUMENTS)
    _render_spark_conf(definition.spark_conf)
    for name in definition.connection_names:
        required_text(name, "Glue job connection name")


def _render_spark_conf(values: dict[str, str] | None) -> str:
    spark_conf = dict(ICEBERG_SPARK_CONF)
    if values is not None:
        if not isinstance(values, dict):
            raise ValueError("Glue job spark_conf must be a mapping")
        overlap = sorted(set(values) & set(ICEBERG_SPARK_CONF))
        if overlap:
            joined = ", ".join(overlap)
            raise ValueError(f"Glue job spark_conf cannot override adapter-owned Iceberg Spark conf: {joined}")
        spark_conf.update({str(key): str(value) for key, value in values.items()})
    return " --conf ".join(f"{key}={value}" for key, value in sorted(spark_conf.items()))
