"""Platform-neutral reporting artifact models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardQuery:
    name: str
    title: str
    visualization: str
    sql: str
