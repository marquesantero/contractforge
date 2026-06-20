"""AWS-owned secret placeholder handling for rendered Glue artifacts.

The AWS adapter renders a static Glue script that is published to S3, so baking
a real credential into that artifact would persist it in object storage. The
strategy is therefore to *keep secrets out of the artifact*: the contract's
``{{ secret:scope/key }}`` placeholder is rendered as a runtime call that
resolves against AWS Secrets Manager when the Glue job runs.

``scope`` maps to the secret id/name and ``key`` to a field inside the secret
JSON document (how Glue JDBC connections store ``username``/``password``).
Whole secret strings are also supported.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SECRET_PLACEHOLDER_RE = re.compile(r"\{\{\s*secret:[^}]+\}\}", re.IGNORECASE)

# Runtime-resolved placeholder the core emits for source.auth.type='rds_iam'.
# It is not an inline credential: the AWS adapter renders a runtime RDS IAM
# token generation for it (see contractforge_aws.sources.rds_iam).
RDS_IAM_TOKEN_PLACEHOLDER = "{{rds_iam_token}}"

# JDBC option keys whose value must never be a literal in a published artifact.
_SENSITIVE_OPTION_KEYS = ("password", "sfpassword")
# Detects ``scheme://user:password@host`` style inline credentials.
_URL_INLINE_CREDENTIALS_RE = re.compile(r"://[^/@\s]+:[^/@\s]+@")


def is_rds_iam_options(options: Mapping[str, Any]) -> bool:
    """Return whether JDBC options use the core's RDS IAM token placeholder."""

    return options.get("password") == RDS_IAM_TOKEN_PLACEHOLDER


def contains_secret_placeholder(value: Any) -> bool:
    """Return True if a string (or any nested string) holds a secret placeholder."""

    if isinstance(value, Mapping):
        return any(contains_secret_placeholder(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_secret_placeholder(item) for item in value)
    if isinstance(value, str):
        return SECRET_PLACEHOLDER_RE.search(value) is not None
    return False


def secret_placeholder_refs(value: str) -> tuple[tuple[str, str], ...]:
    """Return the ``(scope, key)`` references found in a string, in order."""

    return tuple(_parse_placeholder(match.group(0)) for match in SECRET_PLACEHOLDER_RE.finditer(value))


def render_secret_aware_literal(value: str) -> str:
    """Render a Python expression for an option value, never inlining secrets.

    Plain values become a ``repr`` literal. Values that embed one or more
    ``{{ secret:scope/key }}`` placeholders become a concatenation where each
    placeholder is replaced by a ``_cf_resolve_secret(scope, key)`` call that
    runs inside the Glue job, so the literal credential never reaches S3.
    """

    if not SECRET_PLACEHOLDER_RE.search(value):
        return repr(value)
    parts: list[str] = []
    cursor = 0
    for match in SECRET_PLACEHOLDER_RE.finditer(value):
        if match.start() > cursor:
            parts.append(repr(value[cursor : match.start()]))
        scope, key = _parse_placeholder(match.group(0))
        parts.append(f"_cf_resolve_secret({scope!r}, {key!r})")
        cursor = match.end()
    if cursor < len(value):
        parts.append(repr(value[cursor:]))
    return " + ".join(parts)


def assert_no_inline_jdbc_secrets(options: Mapping[str, Any]) -> None:
    """Refuse JDBC options that would publish a raw credential to S3.

    Credentials must be expressed as ``{{ secret:scope/key }}`` placeholders so
    they resolve at job runtime via Secrets Manager instead of being baked into
    the rendered Glue script.
    """

    for key in _SENSITIVE_OPTION_KEYS:
        value = options.get(key)
        if value is None:
            continue
        if contains_secret_placeholder(value) or value == RDS_IAM_TOKEN_PLACEHOLDER:
            continue
        raise ValueError(
            f"JDBC '{key}' must be provided via a {{{{ secret:scope/key }}}} placeholder so the credential "
            "is resolved from AWS Secrets Manager at runtime instead of being baked into the published Glue script."
        )
    url = str(options.get("url") or "")
    if _URL_INLINE_CREDENTIALS_RE.search(url) and not contains_secret_placeholder(url):
        raise ValueError(
            "JDBC url embeds inline credentials; move them to auth using {{ secret:scope/key }} placeholders "
            "so they are not baked into the published Glue script."
        )


def render_secret_resolver_helper() -> str:
    """Render the Glue-runtime ``_cf_resolve_secret`` helper definition."""

    return "\n".join(
        [
            "_CF_SECRETS_MANAGER_CLIENT = None",
            "",
            "",
            "def _cf_resolve_secret(secret_id, json_key):",
            '    """Resolve a secret from AWS Secrets Manager at Glue job runtime."""',
            "    global _CF_SECRETS_MANAGER_CLIENT",
            "    if _CF_SECRETS_MANAGER_CLIENT is None:",
            "        _CF_SECRETS_MANAGER_CLIENT = boto3.client('secretsmanager')",
            "    secret_string = _CF_SECRETS_MANAGER_CLIENT.get_secret_value(SecretId=secret_id)['SecretString']",
            "    try:",
            "        document = json.loads(secret_string)",
            "    except (TypeError, ValueError):",
            "        return secret_string",
            "    if isinstance(document, dict) and json_key in document:",
            "        return document[json_key]",
            "    return secret_string",
            "",
        ]
    )


def _parse_placeholder(placeholder: str) -> tuple[str, str]:
    inner = placeholder.strip()[2:-2].strip()
    ref = inner[len("secret:") :].strip() if inner.lower().startswith("secret:") else inner
    if "/" not in ref:
        raise ValueError("Secret placeholder must use format {{ secret:scope/key }}")
    scope, key = (part.strip() for part in ref.split("/", 1))
    if not scope or not key:
        raise ValueError("Secret placeholder requires non-empty scope and key")
    return scope, key
