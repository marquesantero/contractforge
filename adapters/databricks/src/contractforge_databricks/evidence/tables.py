"""Databricks implementation notes for the core evidence model."""

from __future__ import annotations

from contractforge_core.evidence import EVIDENCE_TABLES


def evidence_table_names(catalog: str, schema: str) -> dict[str, str]:
    return {name: f"{catalog}.{schema}.{table}" for name, table in EVIDENCE_TABLES.items()}


def render_evidence_table_notes(*, catalog: str = "main", schema: str = "ops") -> str:
    lines = [
        "-- Databricks evidence table mapping.",
        "-- These notes are intentionally non-executing review artifacts.",
        "",
    ]
    for name, table in evidence_table_names(catalog, schema).items():
        lines.append(f"-- {name}: {table}")
    return "\n".join(lines) + "\n"
