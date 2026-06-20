"""Planner result and abstract execution plan models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PlanningStatus = Literal[
    "SUPPORTED",
    "SUPPORTED_WITH_WARNINGS",
    "REVIEW_REQUIRED",
    "UNSUPPORTED",
]


@dataclass(frozen=True)
class PlanningBlocker:
    code: str
    message: str


@dataclass(frozen=True)
class PlanningWarning:
    code: str
    message: str


@dataclass(frozen=True)
class ExecutionStep:
    name: str
    intent: str


@dataclass(frozen=True)
class ExecutionPlan:
    platform: str
    steps: tuple[ExecutionStep, ...]
    evidence_required: bool = True


@dataclass(frozen=True)
class PlanningResult:
    status: PlanningStatus
    plan: ExecutionPlan | None
    blockers: tuple[PlanningBlocker, ...] = ()
    warnings: tuple[PlanningWarning, ...] = ()

