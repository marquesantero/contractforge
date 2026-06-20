"""Pydantic models for portable execution planning options."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator

from contractforge_core.config import VALID_IDEMPOTENCY_POLICIES
from contractforge_core.contracts.base import StrictContractModel, contract_validation_error


class ExecutionWindowItemContractModel(StrictContractModel):
    start: str
    end: str
    label: str | None = None


class ExecutionWindowContractModel(StrictContractModel):
    column: str
    windows: list[ExecutionWindowItemContractModel] | None = None
    start: str | None = None
    end: str | None = None
    every: str | None = None
    stop_on_failure: bool = True


class ExecutionCatchupContractModel(StrictContractModel):
    enabled: bool = False
    column: str | None = None
    start: str | None = None
    end: str | None = None
    every: str | None = None
    stop_on_failure: bool = True


ExecutionFreshness = Literal["batch", "near_real_time", "real_time"]
ExecutionPreference = Literal["available_now", "continuous", "event_driven", "scheduled"]
ExecutionFallback = Literal["batch_incremental", "fail", "review_required", "scheduled"]


class ExecutionContractModel(StrictContractModel):
    freshness: ExecutionFreshness | None = None
    latency_target: str | None = None
    preferred: ExecutionPreference | None = None
    fallback: ExecutionFallback | None = None
    window: ExecutionWindowContractModel | None = None
    catchup: ExecutionCatchupContractModel | None = None


def validate_execution_contract(value: Any) -> dict[str, Any]:
    if value is None or not isinstance(value, dict):
        return value
    try:
        return ExecutionContractModel.model_validate(value).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="execution") from exc


def validate_idempotency_policy(value: str | None) -> str | None:
    if value is None:
        return value
    if value not in VALID_IDEMPOTENCY_POLICIES:
        raise ValueError(f"must be one of {sorted(VALID_IDEMPOTENCY_POLICIES)}")
    return value
