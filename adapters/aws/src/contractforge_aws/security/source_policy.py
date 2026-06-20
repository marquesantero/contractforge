"""AWS source-level security policy checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from contractforge_core.connectors import (
    JDBC_CONNECTORS,
    is_http_file_source,
    is_rest_api_connector,
    jdbc_common_options,
)
from contractforge_aws.security.http_safety import validate_http_target
from contractforge_aws.security.secrets import assert_no_inline_jdbc_secrets, contains_secret_placeholder

# REST/HTTP auth fields whose value must never be a literal in a published artifact.
_SENSITIVE_AUTH_TOKENS = ("token", "secret", "password", "api_key", "apikey", "private_key")
_SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "api-key",
        "x-auth-token",
        "x-access-token",
        "cookie",
        "set-cookie",
    }
)


@dataclass(frozen=True)
class SourceSecurityRule:
    applies: Callable[[dict[str, Any]], bool]
    validate: Callable[[dict[str, Any]], None]


def validate_source_security(source: dict[str, Any]) -> None:
    """Validate adapter source security before rendering executable artifacts."""

    for rule in _SOURCE_SECURITY_RULES:
        if rule.applies(source):
            rule.validate(source)


def _is_jdbc_source(source: dict[str, Any]) -> bool:
    source_type = source.get("type")
    connector = source.get("connector")
    return source_type == "jdbc" or connector in JDBC_CONNECTORS


def _is_http_source(source: dict[str, Any]) -> bool:
    return is_http_file_source(source) or is_rest_api_connector(source)


def _validate_jdbc_source(source: dict[str, Any]) -> None:
    assert_no_inline_jdbc_secrets(jdbc_common_options(source))


def _validate_http_source(source: dict[str, Any]) -> None:
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    url = str(source.get("url") or request.get("url") or "").strip()
    if url:
        validate_http_target(url, context="HTTP source URL", resolve=False)
    _assert_no_inline_http_secrets(source)


def _assert_no_inline_http_secrets(source: dict[str, Any]) -> None:
    auth = source.get("auth") if isinstance(source.get("auth"), dict) else {}
    for field in _sensitive_auth_fields(auth):
        value = auth.get(field)
        if value and not contains_secret_placeholder(str(value)):
            raise ValueError(
                f"HTTP/REST auth.{field} must be a {{{{ secret:scope/key }}}} placeholder so the credential is "
                "resolved at runtime instead of being baked into the published Glue script."
            )
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    headers = request.get("headers") if isinstance(request.get("headers"), dict) else {}
    for name, value in headers.items():
        header = str(name).strip().lower()
        if _is_sensitive_header(header) and value and not contains_secret_placeholder(str(value)):
            raise ValueError(
                f"HTTP/REST request.headers.{name} must be a {{{{ secret:scope/key }}}} placeholder so the "
                "credential is resolved at runtime instead of being baked into the published Glue script."
            )


def _is_sensitive_header(name: str) -> bool:
    return name in _SENSITIVE_HEADER_NAMES or "token" in name or "secret" in name


def _sensitive_auth_fields(auth: dict[str, Any]) -> tuple[str, ...]:
    return tuple(name for name in auth if _is_sensitive_auth_field(str(name)))


def _is_sensitive_auth_field(name: str) -> bool:
    normalized = name.strip().lower().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_AUTH_TOKENS)


_SOURCE_SECURITY_RULES = (
    SourceSecurityRule(_is_jdbc_source, _validate_jdbc_source),
    SourceSecurityRule(_is_http_source, _validate_http_source),
)
