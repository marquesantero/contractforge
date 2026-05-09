"""Resolução da SparkSession ativa.

Fornece um proxy `spark` lazy que delega para a sessão ativa em runtime,
suportando tanto Databricks (`databricks.sdk.runtime.spark`) quanto qualquer
ambiente PySpark via `SparkSession.getActiveSession()`. Falha com mensagem
clara quando não há sessão.
"""
from __future__ import annotations

from typing import Any, Optional

from pyspark.sql import DataFrame, SparkSession

_IS_SERVERLESS: Optional[bool] = None


def get_spark() -> SparkSession:
    try:
        from databricks.sdk.runtime import spark as dbx_spark  # type: ignore

        if dbx_spark is not None:
            return dbx_spark  # type: ignore[return-value]
    except Exception:
        pass
    session = SparkSession.getActiveSession()
    if session is None:
        session = SparkSession._instantiatedSession  # type: ignore[attr-defined]
    if session is None:
        raise RuntimeError(
            "Nenhuma SparkSession ativa encontrada. "
            "Inicialize uma sessão (ex.: SparkSession.builder.getOrCreate()) "
            "ou execute dentro de um runtime Databricks antes de chamar o framework."
        )
    return session


class _SparkProxy:
    """Proxy módulo-level: cada acesso resolve a sessão ativa no momento da chamada."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_spark(), name)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "<lakehouse_ingestion._spark.spark proxy>"


spark = _SparkProxy()


def detect_serverless() -> bool:
    global _IS_SERVERLESS
    if _IS_SERVERLESS is not None:
        return _IS_SERVERLESS
    try:
        conf = get_spark().conf
        checks = [
            conf.get("spark.databricks.serverless.enabled", "false").lower() == "true",
            "serverless" in conf.get("spark.databricks.clusterUsageTags.clusterType", "").lower(),
            "serverless" in conf.get("spark.databricks.clusterUsageTags.clusterName", "").lower(),
        ]
        _IS_SERVERLESS = any(checks)
    except Exception:
        _IS_SERVERLESS = False
    return _IS_SERVERLESS


def safe_cache(df: DataFrame, enabled: bool = True) -> DataFrame:
    if not enabled or detect_serverless():
        return df
    try:
        return df.cache()
    except Exception as exc:
        if "NOT_SUPPORTED" in str(exc).upper() or "SERVERLESS" in str(exc).upper():
            return df
        raise


def safe_unpersist(df: DataFrame, enabled: bool = True) -> None:
    if not enabled or detect_serverless():
        return
    try:
        df.unpersist()
    except Exception as exc:
        if "NOT_SUPPORTED" in str(exc).upper() or "SERVERLESS" in str(exc).upper():
            return
        raise
