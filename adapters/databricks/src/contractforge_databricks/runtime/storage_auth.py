"""Databricks runtime object-storage credential helpers."""

from __future__ import annotations

import urllib.parse
from typing import Any

from contractforge_core.connectors import object_storage_provider


def configure_object_storage_access(
    spark: Any,
    source: dict[str, Any],
    options: dict[str, str],
) -> tuple[object | None, dict[str, str]]:
    """Configure adapter-owned Spark storage credentials and return read path/options."""

    provider = object_storage_provider(source)
    path = source.get("path")
    if provider == "s3":
        return path, _configure_s3(spark, source, options)
    if provider == "azure_blob":
        return _configure_azure_blob(spark, source, path), options
    return path, options


def _configure_s3(spark: Any, source: dict[str, Any], options: dict[str, str]) -> dict[str, str]:
    reader_options: dict[str, str] = {}
    for key, value in options.items():
        if key.startswith("fs.s3a.") or key.startswith("spark.hadoop.fs.s3a."):
            _set_conf(spark, key, value)
        else:
            reader_options[key] = value
    auth = _dict(source.get("auth"))
    access_key = auth.get("access_key_id") or auth.get("access_key") or auth.get("aws_access_key_id")
    secret_key = auth.get("secret_access_key") or auth.get("secret_key") or auth.get("aws_secret_access_key")
    session_token = auth.get("session_token") or auth.get("token") or auth.get("aws_session_token")
    if bool(access_key) != bool(secret_key):
        raise ValueError("source.auth for connector=s3 requires access_key_id and secret_access_key together")
    if access_key and secret_key:
        _set_conf(spark, "fs.s3a.access.key", str(access_key))
        _set_conf(spark, "fs.s3a.secret.key", str(secret_key))
        if session_token:
            _set_conf(spark, "fs.s3a.session.token", str(session_token))
            _set_conf(spark, "fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider")
        else:
            _set_conf(spark, "fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    return reader_options


def _configure_azure_blob(spark: Any, source: dict[str, Any], path: object | None) -> object | None:
    auth = _dict(source.get("auth"))
    sas_token = auth.get("sas_token") or auth.get("token")
    if not sas_token:
        return path
    account_url = str(source.get("account_url") or "").strip()
    container = str(source.get("container") or "").strip()
    if account_url or container:
        account = _azure_account_from_url(account_url)
        if not account:
            raise ValueError("source.account_url is required for connector=azure_blob when source.container is used")
        if not container:
            raise ValueError("source.container is required for connector=azure_blob when source.account_url is used")
        _configure_azure_blob_sas(spark, account, container, str(sas_token))
        if path and "://" not in str(path):
            return f"wasbs://{container}@{account}.blob.core.windows.net/{str(path).lstrip('/')}"
        return path
    account, inferred_container = _azure_account_container_from_uri(str(path or ""))
    if not account or not inferred_container:
        raise ValueError(
            "auth.sas_token in connector=azure_blob requires source.account_url/source.container "
            "or path wasbs://container@account.blob.core.windows.net/..."
        )
    _configure_azure_blob_sas(spark, account, inferred_container, str(sas_token))
    return path


def _configure_azure_blob_sas(spark: Any, account: str, container: str, sas_token: str) -> None:
    token = sas_token.strip()
    if token.startswith("?"):
        token = token[1:]
    if not token:
        raise ValueError("auth.sas_token cannot be empty for connector=azure_blob")
    _set_conf(spark, f"fs.azure.sas.{container}.{account}.blob.core.windows.net", token)


def _azure_account_from_url(account_url: str) -> str:
    if not account_url:
        return ""
    parsed = urllib.parse.urlparse(account_url if "://" in account_url else f"https://{account_url}")
    host = parsed.netloc or parsed.path
    return host.split(".", 1)[0].strip()


def _azure_account_container_from_uri(path: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(path)
    if parsed.scheme not in {"wasbs", "wasb", "abfss", "abfs"} or "@" not in parsed.netloc:
        return "", ""
    container, host = parsed.netloc.split("@", 1)
    return host.split(".", 1)[0].strip(), container.strip()


def _set_conf(spark: Any, key: str, value: str) -> None:
    conf = getattr(spark, "conf", None)
    if conf is None or not hasattr(conf, "set"):
        raise RuntimeError("Object-storage source auth requires a Spark session with spark.conf.set")
    try:
        conf.set(key, value)
    except Exception as exc:
        if _is_spark_config_blocked(exc):
            if key.startswith("fs.azure.sas."):
                raise RuntimeError(
                    "Databricks serverless/Spark Connect blocked Spark SAS configuration. "
                    "Use a Unity Catalog External Location or Volume, or configure direct SAS only in a runtime "
                    "where Hadoop config fs.azure.sas.* is allowed."
                ) from exc
            if key.startswith("fs.s3a.") or key.startswith("spark.hadoop.fs.s3a."):
                raise RuntimeError(
                    "Databricks serverless/Spark Connect blocked Spark S3 credential configuration. "
                    "Use a Unity Catalog External Location or Volume, or configure source.auth for S3 only in a "
                    "runtime where Hadoop config fs.s3a.* is allowed."
                ) from exc
        raise


def _is_spark_config_blocked(exc: Exception) -> bool:
    message = str(exc)
    return "CONFIG_NOT_AVAILABLE" in message or "Configuration fs.azure.sas" in message


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
