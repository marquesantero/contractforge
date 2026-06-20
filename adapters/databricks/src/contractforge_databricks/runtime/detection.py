"""Optional runtime detection for active Databricks sessions."""

from __future__ import annotations

import os
from typing import Any

from contractforge_databricks.capabilities import DatabricksCapabilities, evaluate_databricks_capabilities

_DATABRICKS_ENVIRONMENT_KEYS = (
    "DB_INSTANCE_TYPE",
    "DATABRICKS_RUNTIME_VERSION",
    "DATABRICKS_ENV_VERSION",
    "SPARK_CONNECT_MODE_ENABLED",
    "SPARK_EXECUTOR_ATTRIBUTE_POD_NAME",
)

_DATABRICKS_RUNTIME_KEYS = (
    "spark.databricks.workspaceUrl",
    "spark.databricks.clusterUsageTags.clusterId",
    "spark.databricks.clusterUsageTags.clusterName",
    "spark.databricks.clusterUsageTags.clusterType",
    "spark.databricks.clusterUsageTags.jobId",
    "spark.databricks.clusterUsageTags.jobRunId",
    "spark.databricks.job.id",
    "spark.databricks.job.runId",
    "spark.databricks.service.server.enabled",
)


def detect_databricks_capabilities(target_table: str | None = None) -> DatabricksCapabilities:
    """Best-effort detection from an active Spark session.

    The import is intentionally local so importing the adapter package does not
    require PySpark or a Databricks runtime.
    """
    try:
        from pyspark.sql import SparkSession

        spark = SparkSession.getActiveSession()
        if spark is None:
            return evaluate_databricks_capabilities(target_table=target_table, environment=_collect_environment(os.environ))
        return evaluate_databricks_capabilities(
            target_table=target_table,
            spark_version=getattr(spark, "version", None),
            spark_conf=_collect_spark_conf(spark),
            environment=_collect_environment(os.environ),
        )
    except Exception:
        return evaluate_databricks_capabilities(target_table=target_table, environment=_collect_environment(os.environ))


def _collect_environment(environ: Any) -> dict[str, str]:
    collected: dict[str, str] = {}
    for key in _DATABRICKS_ENVIRONMENT_KEYS:
        try:
            value = environ.get(key)
        except Exception:
            value = None
        if value:
            collected[key] = str(value)
    return collected


def _collect_spark_conf(spark: Any) -> dict[str, str]:
    conf = getattr(getattr(spark, "sparkContext", None), "getConf", lambda: None)()
    if conf is None:
        return {}
    collected: dict[str, str] = {}
    for key in _DATABRICKS_RUNTIME_KEYS:
        value = _get_conf_value(conf, key)
        if value is not None:
            collected[key] = value
    for key, value in _iter_conf_items(conf):
        if key.startswith("spark.databricks.") and key not in collected:
            collected[key] = value
    return collected


def _get_conf_value(conf: Any, key: str) -> str | None:
    try:
        value = conf.get(key)
    except TypeError:
        try:
            value = conf.get(key, None)
        except Exception:
            return None
    except Exception:
        return None
    return None if value is None else str(value)


def _iter_conf_items(conf: Any) -> list[tuple[str, str]]:
    try:
        raw_items = conf.getAll()
    except TypeError:
        raw_items = getattr(conf, "getAll", None)
    except Exception:
        return []
    if callable(raw_items):
        try:
            raw_items = raw_items()
        except Exception:
            return []
    items = raw_items.items() if isinstance(raw_items, dict) else raw_items
    result = []
    for item in items or ():
        try:
            key, value = item
        except Exception:
            continue
        if key is not None and value is not None:
            result.append((str(key), str(value)))
    return result
