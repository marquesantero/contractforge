"""Databricks SQL identifier helpers."""

from __future__ import annotations


def quote_identifier(identifier: str) -> str:
    if not identifier or not identifier.strip():
        raise ValueError("identifier must not be empty")
    return f"`{identifier.replace('`', '``')}`"


def quote_table_name(table_name: str) -> str:
    parts = [part.strip() for part in table_name.split(".") if part.strip()]
    if not parts:
        raise ValueError("table name must not be empty")
    return ".".join(quote_identifier(part) for part in parts)

