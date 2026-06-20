"""Smoke-test models and contract factory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_DPU_HOUR_USD = 0.44


@dataclass(frozen=True)
class SmokeConfig:
    account_id: str
    region: str
    bucket: str
    role_name: str
    job_name: str
    max_estimated_cost_usd: float
    dpu_hour_usd: float = DEFAULT_DPU_HOUR_USD
    worker_type: str = "G.1X"
    number_of_workers: int = 2
    timeout_minutes: int = 10

    @property
    def role_arn(self) -> str:
        return f"arn:aws:iam::{self.account_id}:role/{self.role_name}"

    @property
    def source_path(self) -> str:
        return f"s3://{self.bucket}/data/orders/"

    @property
    def warehouse_path(self) -> str:
        return f"s3://{self.bucket}/warehouse/"

    @property
    def artifact_prefix(self) -> str:
        return "artifacts/smoke/orders_overwrite"

    @property
    def script_uri(self) -> str:
        return f"s3://{self.bucket}/{self.artifact_prefix}/lake_cf_aws_smoke_bronze_orders_overwrite.glue_job.py"


def smoke_contract(config: SmokeConfig) -> dict[str, Any]:
    return {
        "source": {"type": "json", "path": config.source_path},
        "target": {"catalog": "lake", "schema": "cf_aws_smoke_bronze", "table": "orders_overwrite"},
        "mode": "scd0_overwrite",
        "extensions": {"aws": {"iceberg": {"warehouse": config.warehouse_path}}},
    }


def estimate_max_cost(config: SmokeConfig) -> float:
    return round((config.number_of_workers * config.dpu_hour_usd * config.timeout_minutes) / 60, 4)


def validate_cost_ceiling(config: SmokeConfig) -> None:
    estimate = estimate_max_cost(config)
    if config.max_estimated_cost_usd < estimate:
        raise ValueError(
            "max_estimated_cost_usd is below the configured Glue timeout ceiling: "
            f"estimated={estimate}, provided={config.max_estimated_cost_usd}"
        )
