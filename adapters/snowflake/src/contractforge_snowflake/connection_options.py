"""Validation for Snowflake connector option maps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

ALLOWED_CONNECT_OPTION_KEYS = frozenset(
    {
        "account",
        "application",
        "authenticator",
        "autocommit",
        "client_fetch_use_mp",
        "client_prefetch_threads",
        "client_session_keep_alive",
        "client_session_keep_alive_heartbeat_frequency",
        "connection_name",
        "converter_class",
        "database",
        "disable_request_pooling",
        "host",
        "insecure_mode",
        "iobound_tpe_limit",
        "login_timeout",
        "network_timeout",
        "numpy",
        "ocsp_fail_open",
        "paramstyle",
        "passcode",
        "passcode_in_password",
        "password",
        "port",
        "private_key",
        "private_key_file",
        "private_key_file_pwd",
        "protocol",
        "proxy_host",
        "proxy_password",
        "proxy_port",
        "proxy_user",
        "region",
        "role",
        "schema",
        "session_parameters",
        "socket_timeout",
        "timezone",
        "token",
        "user",
        "validate_default_parameters",
        "warehouse",
    }
)


def validate_connect_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    if options is None:
        return {}
    if not isinstance(options, Mapping):
        raise ValueError("Snowflake connector options must be a mapping")
    normalized = dict(options)
    unknown = sorted(str(key) for key in normalized if str(key) not in ALLOWED_CONNECT_OPTION_KEYS)
    if unknown:
        allowed = ", ".join(sorted(ALLOWED_CONNECT_OPTION_KEYS))
        rejected = ", ".join(unknown)
        raise ValueError(f"Unsupported Snowflake connector option(s): {rejected}. Allowed keys: {allowed}")
    session_parameters = normalized.get("session_parameters")
    if session_parameters is not None and not isinstance(session_parameters, Mapping):
        raise ValueError("Snowflake connector option session_parameters must be a mapping")
    return normalized
