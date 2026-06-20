"""Databricks SQL fragments for SCD2 late-arriving policies."""

from __future__ import annotations

from contractforge_databricks.sql import quote_identifier


def target_sequence_select(sequence_by: str | None) -> str:
    return f", {quote_identifier(sequence_by)} AS `__tgt_sequence`" if sequence_by else ""


def joined_sequence_select(sequence_by: str | None) -> str:
    return ", t.`__tgt_sequence`" if sequence_by else ""


def reject_guard_join(sequence_by: str | None, policy: str) -> str:
    return " CROSS JOIN reject_late_arriving" if sequence_by and policy == "reject" else ""


def late_arriving_condition(sequence_by: str) -> str:
    column = quote_identifier(sequence_by)
    return f"`__tgt_sequence` IS NOT NULL AND ({column} IS NULL OR {column} <= `__tgt_sequence`)"


def late_arriving_filter(sequence_by: str | None, policy: str) -> str:
    if not sequence_by or policy == "apply":
        return "true"
    if policy not in {"ignore", "reject"}:
        raise ValueError("scd2_late_arriving_policy must be one of apply, ignore, reject")
    return f"NOT ({late_arriving_condition(sequence_by)})"
