"""Fabric-owned secret placeholder rendering for generated notebooks."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from contractforge_fabric.environment import FabricEnvironment

SECRET_PLACEHOLDER_RE = re.compile(r"\{\{\s*secret:[^}]+\}\}", re.IGNORECASE)


def contains_secret_placeholder(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(contains_secret_placeholder(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_secret_placeholder(item) for item in value)
    if isinstance(value, str):
        return SECRET_PLACEHOLDER_RE.search(value) is not None
    return False


def secret_placeholder_refs(value: str) -> tuple[tuple[str, str], ...]:
    return tuple(_parse_placeholder(match.group(0)) for match in SECRET_PLACEHOLDER_RE.finditer(value))


def render_secret_aware_literal(value: str) -> str:
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


def render_secret_resolver_helper(environment: FabricEnvironment) -> str:
    default_vault_url = environment.secret_vault_url
    scoped_vaults = environment.secret_scopes
    return "\n".join(
        [
            f"_CF_DEFAULT_KEY_VAULT_URL = {json.dumps(default_vault_url)}",
            f"_CF_SECRET_SCOPES = {json.dumps(scoped_vaults, sort_keys=True)}",
            "",
            "def _cf_resolve_secret(scope, key):",
            '    """Resolve a ContractForge secret placeholder through Fabric notebookutils."""',
            "    vault_url = _CF_SECRET_SCOPES.get(scope) or _CF_DEFAULT_KEY_VAULT_URL",
            "    if not vault_url:",
            "        raise RuntimeError(",
            "            'Fabric secret placeholder requires environment.secrets.vault_url '",
            "            'or environment.secrets.scopes.<scope> Key Vault URL.'",
            "        )",
            "    return notebookutils.credentials.getSecret(vault_url, key)",
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


__all__ = [
    "SECRET_PLACEHOLDER_RE",
    "contains_secret_placeholder",
    "render_secret_aware_literal",
    "render_secret_resolver_helper",
    "secret_placeholder_refs",
]
