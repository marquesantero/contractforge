"""Databricks-owned secret placeholder resolution."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

SECRET_PLACEHOLDER_RE = re.compile(r"\{\{\s*secret:[^}]+\}\}", re.IGNORECASE)
ENV_OVERRIDE_FLAG = "CONTRACTFORGE_ALLOW_SECRET_ENV_OVERRIDE"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_SENSITIVE_JDBC_OPTION_KEYS = ("password", "sfpassword")
_URL_INLINE_CREDENTIALS_RE = re.compile(r"://[^/@\s]+:[^/@\s]+@")


def contains_secret_placeholder(value: Any) -> bool:
    """Return True if a string or nested value contains a secret placeholder."""

    if isinstance(value, Mapping):
        return any(contains_secret_placeholder(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_secret_placeholder(item) for item in value)
    if isinstance(value, str):
        return SECRET_PLACEHOLDER_RE.search(value) is not None
    return False


def secret_placeholder_refs(value: str) -> tuple[tuple[str, str], ...]:
    """Return ``(scope, key)`` references found in a placeholder-bearing string."""

    return tuple(_parse_secret_ref(match.group(0)[2:-2].strip()) for match in SECRET_PLACEHOLDER_RE.finditer(value))


def assert_no_inline_jdbc_secrets(options: Mapping[str, Any]) -> None:
    """Refuse JDBC options that declare raw credentials in the contract.

    Databricks resolves ``{{ secret:scope/key }}`` placeholders at runtime via
    dbutils. Accepting a literal JDBC password or URL credential would put the
    secret in versioned contract files and review artifacts before the adapter
    ever has a chance to redact it.
    """

    for key in _SENSITIVE_JDBC_OPTION_KEYS:
        if key in options and not contains_secret_placeholder(options[key]) and str(options[key]) != "{{rds_iam_token}}":
            raise ValueError(
                f"JDBC '{key}' must be provided via a {{{{ secret:scope/key }}}} placeholder "
                "or adapter-owned runtime authentication; inline credentials are not accepted."
            )
    url = str(options.get("url") or "")
    if _URL_INLINE_CREDENTIALS_RE.search(url) and not contains_secret_placeholder(url):
        raise ValueError(
            "JDBC url embeds inline credentials; move them to auth using {{ secret:scope/key }} placeholders."
        )


def resolve_databricks_secret_placeholders(value: Any) -> Any:
    """Resolve ``{{ secret:scope/key }}`` placeholders recursively at adapter runtime."""

    if isinstance(value, Mapping):
        return {key: resolve_databricks_secret_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_databricks_secret_placeholders(item) for item in value]
    if isinstance(value, tuple):
        return tuple(resolve_databricks_secret_placeholders(item) for item in value)
    if isinstance(value, str):
        return SECRET_PLACEHOLDER_RE.sub(lambda match: _resolve_secret_token(match.group(0)[2:-2].strip()), value)
    return value


def _env_override_enabled() -> bool:
    """Return True only when CONTRACTFORGE_ALLOW_SECRET_ENV_OVERRIDE is explicitly on.

    Honoring CONTRACTFORGE_SECRET_* env vars by default lets anyone who can
    set cluster environment variables (init scripts, cluster policies) shadow
    a secret coming from dbutils.secrets without an audit trail. Gating the
    behavior behind a single explicit flag keeps the override available for
    runtime token injection (e.g. RDS IAM tokens) while making the resolver
    safe-by-default in shared workspaces.
    """

    raw = os.environ.get(ENV_OVERRIDE_FLAG, "")
    return raw.strip().lower() in _TRUE_VALUES


def _resolve_secret_token(token: str) -> str:
    scope, key = _parse_secret_ref(token)
    if _env_override_enabled():
        env_name = f"CONTRACTFORGE_SECRET_{scope}_{key}".upper().replace("-", "_").replace(".", "_")
        if env_name in os.environ:
            return os.environ[env_name]
    return str(_dbutils().secrets.get(scope=scope, key=key))


def _parse_secret_ref(token: str) -> tuple[str, str]:
    ref = token[len("secret:") :].strip() if token.lower().startswith("secret:") else token.strip()
    if "/" not in ref:
        raise ValueError("Secret placeholder must use format {{ secret:scope/key }}")
    scope, key = [part.strip() for part in ref.split("/", 1)]
    if not scope or not key:
        raise ValueError("Secret placeholder requires non-empty scope and key")
    return scope, key


def _dbutils() -> Any:
    try:
        from IPython import get_ipython  # type: ignore

        shell = get_ipython()
        if shell and "dbutils" in shell.user_ns:
            return shell.user_ns["dbutils"]
    except Exception:
        pass
    raise RuntimeError("Could not resolve dbutils to access Databricks Secrets")
