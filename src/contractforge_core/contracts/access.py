"""Pydantic access contract models."""

from __future__ import annotations

from typing import Any

from pydantic import Field, ValidationError, field_validator, model_validator

from contractforge_core.config import (
    AccessDriftPolicy,
    AccessMode,
    VALID_ACCESS_DRIFT_POLICIES,
    VALID_ACCESS_MODES,
)
from contractforge_core.contracts.base import StrictContractModel, contract_validation_error
from contractforge_core.contracts.governance_common import TargetReferenceContractModel


class AccessPolicyContractModel(StrictContractModel):
    mode: AccessMode = "apply"
    on_drift: AccessDriftPolicy = "warn"
    revoke_unmanaged: bool = False

    @field_validator("mode")
    @classmethod
    def _valid_mode(cls, value: str) -> str:
        if value not in VALID_ACCESS_MODES:
            raise ValueError(f"must be one of {sorted(VALID_ACCESS_MODES)}")
        return value

    @field_validator("on_drift")
    @classmethod
    def _valid_drift(cls, value: str) -> str:
        if value not in VALID_ACCESS_DRIFT_POLICIES:
            raise ValueError(f"must be one of {sorted(VALID_ACCESS_DRIFT_POLICIES)}")
        return value


class AccessGrantContractModel(StrictContractModel):
    principal: str
    privileges: list[str] | str

    @field_validator("principal", mode="after")
    @classmethod
    def _principal_required(cls, value: str) -> str:
        return _required_text(value, "access.grants.principal")

    @field_validator("privileges", mode="after")
    @classmethod
    def _privileges_required(cls, value: list[str] | str) -> list[str] | str:
        _required_list(value, "access.grants.privileges")
        return value


class AppliesToContractModel(StrictContractModel):
    principals: list[str] | str | None = None

    @field_validator("principals", mode="after")
    @classmethod
    def _principals_not_empty(cls, value: list[str] | str | None) -> list[str] | str | None:
        if value is not None:
            _required_list(value, "access.applies_to.principals")
        return value


class RowFilterContractModel(StrictContractModel):
    name: str
    function: str
    columns: list[str] | str
    applies_to: AppliesToContractModel = Field(default_factory=AppliesToContractModel)

    @field_validator("name", "function", mode="after")
    @classmethod
    def _text_required(cls, value: str) -> str:
        return _required_text(value, "access.row_filters")

    @field_validator("columns", mode="after")
    @classmethod
    def _columns_required(cls, value: list[str] | str) -> list[str] | str:
        _required_list(value, "access.row_filters.columns")
        return value


class ColumnMaskContractModel(StrictContractModel):
    column: str
    function: str
    using_columns: list[str] | str | None = None
    applies_to: AppliesToContractModel = Field(default_factory=AppliesToContractModel)

    @field_validator("column", "function", mode="after")
    @classmethod
    def _text_required(cls, value: str) -> str:
        return _required_text(value, "access.column_masks")

    @field_validator("using_columns", mode="after")
    @classmethod
    def _using_columns_not_empty(cls, value: list[str] | str | None) -> list[str] | str | None:
        if value is not None:
            _required_list(value, "access.column_masks.using_columns")
        return value


class AccessContractModel(StrictContractModel):
    target: TargetReferenceContractModel | None = None
    mode: AccessMode | None = None
    on_drift: AccessDriftPolicy | None = None
    revoke_unmanaged: bool | None = None
    access_policy: AccessPolicyContractModel | None = None
    grants: list[AccessGrantContractModel] = Field(default_factory=list)
    row_filters: list[RowFilterContractModel] = Field(default_factory=list)
    column_masks: list[ColumnMaskContractModel] = Field(default_factory=list)

    @field_validator("column_masks", mode="before")
    @classmethod
    def _normalize_column_masks(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return [{**dict(config), "column": column} for column, config in value.items()]

    @model_validator(mode="after")
    def _validate_policy_aliases(self) -> "AccessContractModel":
        if self.mode is not None and self.mode not in VALID_ACCESS_MODES:
            raise ValueError(f"access.mode must be one of {sorted(VALID_ACCESS_MODES)}")
        if self.on_drift is not None and self.on_drift not in VALID_ACCESS_DRIFT_POLICIES:
            raise ValueError(f"access.on_drift must be one of {sorted(VALID_ACCESS_DRIFT_POLICIES)}")
        return self


def validate_access_contract(value: Any) -> dict[str, Any]:
    if value is None or not isinstance(value, dict):
        return value
    if _is_self_wrapped(value, "access"):
        raise ValueError(
            "access.yaml must declare fields at the document root, not under 'access:'."
            " Remove the wrapping 'access:' key and outdent its contents."
        )
    try:
        return AccessContractModel.model_validate(value).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="access") from exc


def _is_self_wrapped(value: dict[str, Any], name: str) -> bool:
    if name not in value:
        return False
    if not isinstance(value[name], dict):
        return False
    return set(value) <= {name, "target", "_metadata"}


def _required_text(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} cannot be empty")
    return text


def _required_list(value: list[str] | str, field: str) -> None:
    items = [value] if isinstance(value, str) else list(value)
    if not items or any(not str(item).strip() for item in items):
        raise ValueError(f"{field} cannot contain empty values")
