"""Platform-neutral diagnostic models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExplainPlanRecord:
    run_id: str
    target_table: str
    source_name: str
    mode: str
    explain_format: str
    plan_text: str
