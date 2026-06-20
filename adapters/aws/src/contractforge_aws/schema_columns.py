"""Helpers for parsing rendered control-table schema declarations."""

from __future__ import annotations


def schema_columns(schema: str) -> list[str]:
    return [part.strip().split()[0].strip("`") for part in schema.split(",") if part.strip()]
