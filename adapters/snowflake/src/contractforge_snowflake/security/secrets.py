"""Snowflake-owned secret placeholder resolution."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

SECRET_PLACEHOLDER_RE = re.compile(r"\{\{\s*secret:[^}]+\}\}", re.IGNORECASE)


def contains_secret_placeholder(value: Any) -> bool:
    """Return True if a value contains a ContractForge secret placeholder."""

    if isinstance(value, Mapping):
        return any(contains_secret_placeholder(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_secret_placeholder(item) for item in value)
    if isinstance(value, str):
        return SECRET_PLACEHOLDER_RE.search(value) is not None
    return False


def resolve_snowflake_secret_placeholders(
    value: Any,
    *,
    secret_getter: Callable[[str], str] | None = None,
) -> Any:
    """Resolve ``{{ secret:snowflake/alias }}`` placeholders recursively."""

    if isinstance(value, Mapping):
        return {key: resolve_snowflake_secret_placeholders(item, secret_getter=secret_getter) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_snowflake_secret_placeholders(item, secret_getter=secret_getter) for item in value]
    if isinstance(value, tuple):
        return tuple(resolve_snowflake_secret_placeholders(item, secret_getter=secret_getter) for item in value)
    if isinstance(value, str):
        return SECRET_PLACEHOLDER_RE.sub(
            lambda match: _resolve_secret_token(match.group(0)[2:-2].strip(), secret_getter=secret_getter),
            value,
        )
    return value


def _resolve_secret_token(token: str, *, secret_getter: Callable[[str], str] | None) -> str:
    scope, alias = _parse_secret_ref(token)
    if scope.lower() != "snowflake":
        raise ValueError("Snowflake secret placeholder must use format {{ secret:snowflake/alias }}")
    getter = secret_getter or get_snowflake_generic_secret_string
    return str(getter(alias))


def _parse_secret_ref(token: str) -> tuple[str, str]:
    ref = token[len("secret:") :].strip() if token.lower().startswith("secret:") else token.strip()
    if "/" not in ref:
        raise ValueError("Secret placeholder must use format {{ secret:snowflake/alias }}")
    scope, alias = [part.strip() for part in ref.split("/", 1)]
    if not scope or not alias:
        raise ValueError("Secret placeholder requires non-empty scope and alias")
    return scope, alias


def get_snowflake_generic_secret_string(alias: str) -> str:
    """Read a Snowflake GENERIC_STRING secret bound to a Python procedure."""

    try:
        from snowflake.snowpark import secrets as snowpark_secrets  # type: ignore

        return str(snowpark_secrets.get_generic_secret_string(alias))
    except Exception as snowpark_error:
        try:
            import _snowflake  # type: ignore

            return str(_snowflake.get_generic_secret_string(alias))
        except Exception as legacy_error:
            raise RuntimeError(
                "Could not resolve Snowflake generic secret. Ensure the procedure declares "
                "SECRETS = ('alias' = DATABASE.SCHEMA.SECRET) and runs inside Snowflake."
            ) from legacy_error or snowpark_error
