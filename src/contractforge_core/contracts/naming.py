"""Pydantic naming contract model."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError, field_validator

from contractforge_core.contracts.base import StrictContractModel, contract_validation_error


class NamingContractModel(StrictContractModel):
    policy: str = "caf_default"
    display_name: str | None = None
    logical_name: str | None = None
    slug: str | None = None
    contract_basename: str | None = None
    bundle_name: str | None = None
    job_name: str | None = None
    task_key: str | None = None
    artifact_prefix: str | None = None
    preserve_target_identifiers: bool = True

    @field_validator("policy")
    @classmethod
    def _valid_policy(cls, value: str) -> str:
        if value not in {"caf_default", "custom"}:
            raise ValueError("must be one of ['caf_default', 'custom']")
        return value


def validate_naming_contract(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("naming must be an object")
    try:
        return NamingContractModel.model_validate(value).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="naming") from exc
