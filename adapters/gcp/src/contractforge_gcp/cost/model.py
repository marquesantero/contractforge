"""GCP BigQuery cost model inputs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    bytes_processed_per_tib_rate: float | None = None
    slot_hour_rate: float | None = None
    currency: str = "USD"

    @property
    def enabled(self) -> bool:
        return self.bytes_processed_per_tib_rate is not None or self.slot_hour_rate is not None
