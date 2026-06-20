"""Runtime classification helpers for Databricks capability evaluation."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.capabilities.models import CapabilityEvidence, RuntimeKind

SERVERLESS_TRUE_KEYS = (
    "spark.databricks.serverless.enabled",
    "spark.databricks.compute.serverless.enabled",
)
DATABRICKS_ENVIRONMENT_KEYS = (
    "DB_INSTANCE_TYPE",
    "DATABRICKS_RUNTIME_VERSION",
    "DATABRICKS_ENV_VERSION",
    "SPARK_CONNECT_MODE_ENABLED",
    "SPARK_EXECUTOR_ATTRIBUTE_POD_NAME",
)
CLASSIC_CLUSTER_KEYS = (
    "spark.databricks.clusterUsageTags.clusterId",
    "spark.databricks.clusterUsageTags.clusterName",
    "spark.databricks.clusterUsageTags.clusterType",
)
JOB_METADATA_KEY_FRAGMENTS = ("job", "run")


def runtime_kind(
    *,
    runtime_type: str | None,
    spark_conf: dict[str, str],
    environment: dict[str, str] | None = None,
) -> RuntimeKind:
    normalized = (runtime_type or "").strip().lower()
    if normalized in {"serverless", "serverless_job", "databricks_serverless"}:
        return "databricks_serverless"
    if normalized == "classic":
        return "databricks_classic" if has_databricks_conf(spark_conf) else "spark"
    if normalized in {"classic_cluster", "classic_existing_cluster", "databricks_classic"}:
        return "databricks_classic"
    if is_serverless_runtime(spark_conf, environment=environment):
        return "databricks_serverless"
    if has_databricks_conf(spark_conf):
        return "databricks_classic"
    return "unknown" if not spark_conf else "spark"


def runtime_evidence(
    *,
    runtime_kind: RuntimeKind,
    spark_version: str | None,
    spark_conf: dict[str, str],
    environment: dict[str, str] | None = None,
) -> tuple[CapabilityEvidence, ...]:
    evidence = [_e("runtime_kind", "Runtime classified from provided evidence.", runtime_kind)]
    if spark_version:
        evidence.append(_e("spark_version", "Spark version was provided.", spark_version))
    for key in sorted(spark_conf):
        if key.startswith("spark.databricks."):
            evidence.append(_e("spark_conf", "Databricks Spark configuration key detected.", key))
    for key in sorted(environment or {}):
        if key in DATABRICKS_ENVIRONMENT_KEYS:
            evidence.append(_e("environment", "Databricks runtime environment key detected.", key))
    return tuple(evidence)


def has_databricks_conf(spark_conf: dict[str, str]) -> bool:
    return any(key.startswith("spark.databricks.") and str(value).strip() for key, value in spark_conf.items())


def is_serverless_runtime(
    spark_conf: dict[str, str],
    *,
    environment: dict[str, str] | None = None,
) -> bool:
    return is_serverless_conf(spark_conf) or is_serverless_environment(environment or {})


def is_serverless_conf(spark_conf: dict[str, str]) -> bool:
    normalized = {str(key): str(value) for key, value in spark_conf.items()}
    if any(normalized.get(key, "").strip().lower() == "true" for key in SERVERLESS_TRUE_KEYS):
        return True
    if any(key.startswith("spark.databricks.") and "serverless" in value.lower() for key, value in normalized.items()):
        return True
    return _looks_like_databricks_serverless_job(normalized)


def is_serverless_environment(environment: dict[str, str]) -> bool:
    normalized = {str(key): str(value) for key, value in environment.items()}
    return any(key in DATABRICKS_ENVIRONMENT_KEYS and "serverless" in value.lower() for key, value in normalized.items())


def is_three_part_name(target_table: str | None) -> bool:
    return bool(target_table and len([part for part in target_table.split(".") if part.strip()]) >= 3)


def _looks_like_databricks_serverless_job(spark_conf: dict[str, str]) -> bool:
    if not has_databricks_conf(spark_conf):
        return False
    if any(spark_conf.get(key, "").strip() for key in CLASSIC_CLUSTER_KEYS):
        return False
    return any(
        key.startswith("spark.databricks.")
        and all(fragment in key.lower() for fragment in JOB_METADATA_KEY_FRAGMENTS)
        and str(value).strip()
        for key, value in spark_conf.items()
    )


def _e(source: str, message: str, value: Any = None) -> CapabilityEvidence:
    return CapabilityEvidence(source=source, message=message, value=None if value is None else str(value))
