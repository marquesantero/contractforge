"""Materialize RDS IAM JDBC tokens at adapter runtime.

The core's ``rds_iam_review_options`` only writes a placeholder password
(``{{rds_iam_token}}``) plus three ``contractforge.rdsIamHost / Port /
Region`` metadata options. At runtime the Databricks adapter is the
layer that has the AWS credentials and the network reach to actually
mint the IAM auth token, so the materialization belongs here.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Mapping

from contractforge_core.connectors import generate_rds_iam_auth_token

RDS_IAM_TOKEN_PLACEHOLDER = "{{rds_iam_token}}"
_HOST_OPTION = "contractforge.rdsIamHost"
_PORT_OPTION = "contractforge.rdsIamPort"
_REGION_OPTION = "contractforge.rdsIamRegion"
_METADATA_OPTIONS = (_HOST_OPTION, _PORT_OPTION, _REGION_OPTION)
_TOKEN_TTL_SECONDS = 14 * 60
_TOKEN_CACHE: dict[str, tuple[float, str]] = {}


def materialize_rds_iam_options(
    options: Mapping[str, str],
    *,
    auth: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Replace the RDS IAM placeholder with a freshly minted IAM auth token.

    Returns a new options dict with the contractforge.rdsIam* metadata
    keys removed. If the placeholder is not present, the options are
    returned untouched so non-IAM JDBC sources are unaffected.
    """

    options_dict = dict(options)
    if options_dict.get("password") != RDS_IAM_TOKEN_PLACEHOLDER:
        for key in _METADATA_OPTIONS:
            options_dict.pop(key, None)
        return options_dict
    host = options_dict.pop(_HOST_OPTION, None)
    port = options_dict.pop(_PORT_OPTION, None)
    region = options_dict.pop(_REGION_OPTION, None)
    if not host or not port or not region:
        raise ValueError(
            "RDS IAM materialization requires contractforge.rdsIamHost,"
            " contractforge.rdsIamPort and contractforge.rdsIamRegion"
            " (produced by the core for source.auth.type='rds_iam')"
        )
    auth_dict = dict(auth or {})
    username = str(options_dict.get("user") or auth_dict.get("username") or "")
    if not username:
        raise ValueError("RDS IAM auth requires a JDBC user or source.auth.username")
    host_text = str(host)
    port_int = int(port)
    region_text = str(region)
    access_key = auth_dict.get("access_key_id")
    secret_key = auth_dict.get("secret_access_key")
    session_token = auth_dict.get("session_token")
    token = _cached_token(
        host=host_text,
        port=port_int,
        region=region_text,
        username=username,
        access_key=str(access_key or ""),
        secret_key=str(secret_key or ""),
        session_token=str(session_token or ""),
    )
    if not token:
        if access_key and secret_key:
            token = generate_rds_iam_auth_token(
                host=host_text,
                port=port_int,
                region=region_text,
                username=username,
                access_key=str(access_key),
                secret_key=str(secret_key),
                session_token=str(session_token) if session_token else None,
            )
        else:
            token = _boto3_rds_iam_token(host=host_text, port=port_int, region=region_text, username=username)
        _store_token(
            host=host_text,
            port=port_int,
            region=region_text,
            username=username,
            access_key=str(access_key or ""),
            secret_key=str(secret_key or ""),
            session_token=str(session_token or ""),
            token=token,
        )
    options_dict["password"] = token
    return options_dict


def _cache_key(
    *,
    host: str,
    port: int,
    region: str,
    username: str,
    access_key: str,
    secret_key: str,
    session_token: str,
) -> str:
    digest = hashlib.sha256()
    for component in (host, str(port), region, username, access_key, secret_key, session_token):
        digest.update(component.encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def _cached_token(
    *,
    host: str,
    port: int,
    region: str,
    username: str,
    access_key: str,
    secret_key: str,
    session_token: str,
) -> str | None:
    key = _cache_key(
        host=host,
        port=port,
        region=region,
        username=username,
        access_key=access_key,
        secret_key=secret_key,
        session_token=session_token,
    )
    cached = _TOKEN_CACHE.get(key)
    if not cached:
        return None
    created_at, token = cached
    if time.time() - created_at >= _TOKEN_TTL_SECONDS:
        _TOKEN_CACHE.pop(key, None)
        return None
    return token


def _store_token(
    *,
    host: str,
    port: int,
    region: str,
    username: str,
    access_key: str,
    secret_key: str,
    session_token: str,
    token: str,
) -> None:
    key = _cache_key(
        host=host,
        port=port,
        region=region,
        username=username,
        access_key=access_key,
        secret_key=secret_key,
        session_token=session_token,
    )
    _TOKEN_CACHE[key] = (time.time(), token)


def _boto3_rds_iam_token(*, host: str, port: int, region: str, username: str) -> str:
    try:
        import boto3  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on runtime image
        raise ValueError(
            "RDS IAM auth requires either source.auth.access_key_id/source.auth.secret_access_key "
            "or Databricks cluster AWS credentials with boto3 available"
        ) from exc
    try:
        client = boto3.Session(region_name=region).client("rds", region_name=region)
        return str(
            client.generate_db_auth_token(
                DBHostname=host,
                Port=port,
                DBUsername=username,
                Region=region,
            )
        )
    except Exception as exc:
        raise ValueError(
            "RDS IAM auth could not generate a token from Databricks cluster AWS credentials; "
            "configure an instance profile/default AWS credential chain or declare "
            "source.auth.access_key_id/source.auth.secret_access_key as secret placeholders"
        ) from exc
