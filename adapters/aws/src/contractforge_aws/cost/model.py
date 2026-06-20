"""AWS Glue cost model for evidence-query estimates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    dpu_hour_usd: float | None = None
    currency: str = "USD"

    @property
    def enabled(self) -> bool:
        return self.dpu_hour_usd is not None

    @property
    def hourly_rate(self) -> float | None:
        return None if self.dpu_hour_usd is None else float(self.dpu_hour_usd)
