"""Platform-neutral AWS RDS IAM auth helpers."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
import urllib.parse
from typing import Any

_JDBC_HOST_RE = re.compile(r"^jdbc:(?P<dialect>[a-z0-9]+)://(?P<host>[^/:?;]+)(?::(?P<port>\d+))?", re.IGNORECASE)
_DEFAULT_PORTS = {"mariadb": 3306, "mysql": 3306, "postgres": 5432, "postgresql": 5432}


def parse_jdbc_host_port(url: str, default_port: int = 5432) -> tuple[str, int]:
    match = _JDBC_HOST_RE.match(url)
    if not match:
        raise ValueError("JDBC URL must use jdbc:<dialect>://host[:port]/database for RDS IAM")
    dialect = match.group("dialect").lower()
    return match.group("host"), int(match.group("port") or _DEFAULT_PORTS.get(dialect, default_port))


def infer_aws_region_from_rds_host(host: str) -> str | None:
    match = re.search(r"\.([a-z]{2}-[a-z]+-\d)\.(?:rds|rdsrelay)\.", host)
    return match.group(1) if match else None


def rds_iam_review_options(url: str, *, auth: dict[str, Any], username: str | None = None) -> dict[str, str]:
    user = str(auth.get("username") or username or "").strip()
    if not user:
        raise ValueError("JDBC RDS IAM auth requires auth.username")
    host, port = parse_jdbc_host_port(url, int(auth.get("port") or 5432))
    region = str(auth.get("region") or infer_aws_region_from_rds_host(host) or "").strip()
    if not region:
        raise ValueError("JDBC RDS IAM auth requires auth.region when region cannot be inferred from host")
    return {
        "user": user,
        "password": "{{rds_iam_token}}",
        "ssl": "true",
        "sslmode": str(auth.get("sslmode") or "require"),
        "contractforge.rdsIamHost": host,
        "contractforge.rdsIamPort": str(port),
        "contractforge.rdsIamRegion": region,
    }


def generate_rds_iam_auth_token(
    *,
    host: str,
    port: int,
    region: str,
    username: str,
    access_key: str,
    secret_key: str,
    session_token: str | None = None,
    now: dt.datetime | None = None,
) -> str:
    current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    amz_date = current.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = current.strftime("%Y%m%d")
    service = "rds-db"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    endpoint = f"{host}:{int(port)}"
    query: list[tuple[str, Any]] = [
        ("Action", "connect"),
        ("DBUser", username),
        ("X-Amz-Algorithm", "AWS4-HMAC-SHA256"),
        ("X-Amz-Credential", f"{access_key}/{credential_scope}"),
        ("X-Amz-Date", amz_date),
        ("X-Amz-Expires", "900"),
        ("X-Amz-SignedHeaders", "host"),
    ]
    if session_token:
        query.append(("X-Amz-Security-Token", session_token))
    canonical_query = "&".join(f"{_quote(key)}={_quote(value)}" for key, value in sorted(query))
    canonical_request = "\n".join(["GET", "/", canonical_query, f"host:{endpoint}\n", "host", hashlib.sha256(b"").hexdigest()])
    string_to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, credential_scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()]
    )
    signing_key = _signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{endpoint}/?{canonical_query}&X-Amz-Signature={signature}"


def _signature_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    key_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    key_region = _sign(key_date, region)
    key_service = _sign(key_region, service)
    return _sign(key_service, "aws4_request")


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _quote(value: Any) -> str:
    return urllib.parse.quote(str(value), safe="-_.~")
