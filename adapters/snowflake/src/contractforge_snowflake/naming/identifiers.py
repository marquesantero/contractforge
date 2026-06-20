"""Snowflake identifier rendering.

The adapter renders quoted identifiers for generated SQL so mixed case,
reserved words and embedded quotes cannot change semantics.
"""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract


def quote_identifier(value: object) -> str:
    text = str(value)
    if not text:
        raise ValueError("Snowflake identifier cannot be empty")
    return '"' + text.replace('"', '""') + '"'


def quote_multipart_identifier(value: str) -> str:
    parts = [part.strip() for part in value.split(".") if part.strip()]
    if not parts:
        raise ValueError("Snowflake object name cannot be empty")
    return ".".join(quote_identifier(part) for part in parts)


def snowflake_target_name(contract: SemanticContract) -> str:
    parts = [part for part in (contract.target.namespace or "").split(".") if part]
    parts.append(contract.target.name)
    return ".".join(quote_identifier(part) for part in parts)
