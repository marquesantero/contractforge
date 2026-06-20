"""Databricks logical cost model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    dbu_per_hour: float | None = None
    currency_per_dbu: float | None = None
    currency: str = "USD"

    @property
    def enabled(self) -> bool:
        return self.dbu_per_hour is not None and self.currency_per_dbu is not None

    @property
    def hourly_rate(self) -> float | None:
        if not self.enabled:
            return None
        return float(self.dbu_per_hour or 0.0) * float(self.currency_per_dbu or 0.0)
