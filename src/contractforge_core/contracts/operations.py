"""Pydantic operations contract models."""

from __future__ import annotations

from typing import Any

from pydantic import Field, ValidationError, field_validator

from contractforge_core.config import VALID_CRITICALITY_LEVELS, VALID_EXPECTED_FREQUENCIES
from contractforge_core.contracts.base import StrictContractModel, contract_validation_error
from contractforge_core.contracts.governance_common import TargetReferenceContractModel


class OperationsOwnershipContractModel(StrictContractModel):
    business_owner: str | None = None
    technical_owner: str | None = None
    steward: str | None = None
    support_group: str | None = None
    escalation_group: str | None = None


class OperationsBlockContractModel(StrictContractModel):
    criticality: str | None = None
    expected_frequency: str | None = None
    freshness_sla_minutes: int | None = Field(default=None, gt=0)
    alert_on_failure: bool = False
    alert_on_quality_fail: bool = False
    runbook_url: str | None = None
    owners: list[str] | str | None = None
    groups: list[str] | str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)

    @field_validator("criticality")
    @classmethod
    def _valid_criticality(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_CRITICALITY_LEVELS:
            raise ValueError(f"must be one of {sorted(VALID_CRITICALITY_LEVELS)}")
        return value

    @field_validator("expected_frequency")
    @classmethod
    def _valid_frequency(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_EXPECTED_FREQUENCIES:
            raise ValueError(f"must be one of {sorted(VALID_EXPECTED_FREQUENCIES)}")
        return value


class OperationsContractModel(OperationsBlockContractModel):
    target: TargetReferenceContractModel | None = None
    ownership: OperationsOwnershipContractModel = Field(default_factory=OperationsOwnershipContractModel)
    operations: OperationsBlockContractModel | None = None


def validate_operations_contract(value: Any) -> dict[str, Any]:
    if value is None or not isinstance(value, dict):
        return value
    _reject_operations_wrapper(value)
    value = _normalize_flat_ownership(value)
    try:
        return OperationsContractModel.model_validate(value).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="operations") from exc


def _reject_operations_wrapper(value: dict[str, Any]) -> None:
    nested = value.get("operations")
    if isinstance(nested, dict) and not (set(value) - {"target", "operations"}):
        raise ValueError("operations.yaml must declare fields at the document root, not under 'operations:'")


def _normalize_flat_ownership(value: dict[str, Any]) -> dict[str, Any]:
    ownership_fields = {"business_owner", "technical_owner", "steward", "support_group", "escalation_group"}
    flat = {field: value[field] for field in ownership_fields if field in value}
    if not flat:
        return value
    normalized = {key: item for key, item in value.items() if key not in ownership_fields}
    ownership = dict(normalized.get("ownership") or {})
    ownership.update(flat)
    normalized["ownership"] = ownership
    return normalized
