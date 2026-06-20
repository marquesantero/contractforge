"""Pydantic annotation contract models."""

from __future__ import annotations

from typing import Any

from pydantic import Field, ValidationError, field_validator

from contractforge_core.config import (
    GovernanceFailurePolicy,
    VALID_GOVERNANCE_FAILURE_POLICIES,
    VALID_PII_TYPES,
    VALID_SENSITIVITY_LEVELS,
)
from contractforge_core.contracts.base import StrictContractModel, contract_validation_error
from contractforge_core.contracts.governance_common import (
    TargetReferenceContractModel,
    non_empty,
)


class DeprecatedContractModel(StrictContractModel):
    since: str
    replacement: str
    removal_date: str | None = None

    @field_validator("since", "replacement", "removal_date", mode="after")
    @classmethod
    def _non_empty_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError("must not be empty")
        return text


class PiiContractModel(StrictContractModel):
    enabled: bool = True
    type: str = "unknown"
    sensitivity: str = "internal"

    @field_validator("type")
    @classmethod
    def _valid_type(cls, value: str) -> str:
        if value not in VALID_PII_TYPES:
            raise ValueError(f"must be one of {sorted(VALID_PII_TYPES)}")
        return value

    @field_validator("sensitivity")
    @classmethod
    def _valid_sensitivity(cls, value: str) -> str:
        if value not in VALID_SENSITIVITY_LEVELS:
            raise ValueError(f"must be one of {sorted(VALID_SENSITIVITY_LEVELS)}")
        return value


class TableAnnotationsContractModel(StrictContractModel):
    description: str | None = None
    aliases: list[str] | str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)
    deprecated: DeprecatedContractModel | None = None

    @field_validator("description", mode="after")
    @classmethod
    def _empty_description(cls, value: str | None) -> str | None:
        return non_empty(value)

    @field_validator("aliases", mode="after")
    @classmethod
    def _aliases_not_empty(cls, value: list[str] | str | None) -> list[str] | str | None:
        _validate_aliases(value, "annotations.table.aliases")
        return value

    @field_validator("tags")
    @classmethod
    def _tags_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_tags(value, "annotations.table.tags")
        return value


class ColumnAnnotationsContractModel(StrictContractModel):
    description: str | None = None
    aliases: list[str] | str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)
    pii: PiiContractModel | None = None
    deprecated: DeprecatedContractModel | None = None

    @field_validator("description", mode="after")
    @classmethod
    def _empty_description(cls, value: str | None) -> str | None:
        return non_empty(value)

    @field_validator("aliases", mode="after")
    @classmethod
    def _aliases_not_empty(cls, value: list[str] | str | None) -> list[str] | str | None:
        _validate_aliases(value, "annotations.columns.aliases")
        return value

    @field_validator("tags")
    @classmethod
    def _tags_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_tags(value, "annotations.columns.tags")
        return value


class AnnotationsContractModel(StrictContractModel):
    target: TargetReferenceContractModel | None = None
    policy: GovernanceFailurePolicy = "warn"
    table: TableAnnotationsContractModel = Field(default_factory=TableAnnotationsContractModel)
    columns: dict[str, ColumnAnnotationsContractModel] = Field(default_factory=dict)

    @field_validator("policy")
    @classmethod
    def _valid_policy(cls, value: str) -> str:
        if value not in VALID_GOVERNANCE_FAILURE_POLICIES:
            raise ValueError(f"must be one of {sorted(VALID_GOVERNANCE_FAILURE_POLICIES)}")
        return value

    @field_validator("columns")
    @classmethod
    def _valid_columns(cls, value: dict[str, ColumnAnnotationsContractModel]) -> dict[str, ColumnAnnotationsContractModel]:
        invalid = [name for name in value if not str(name).strip()]
        if invalid:
            raise ValueError("cannot contain empty column names")
        return value


def validate_annotations_contract(value: Any) -> dict[str, Any]:
    if value is None or not isinstance(value, dict):
        return value
    if _is_self_wrapped(value, "annotations"):
        raise ValueError(
            "annotations.yaml must declare fields at the document root, not under 'annotations:'."
            " Remove the wrapping 'annotations:' key and outdent its contents."
        )
    try:
        return AnnotationsContractModel.model_validate(value).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="annotations") from exc


def _is_self_wrapped(value: dict[str, Any], name: str) -> bool:
    if name not in value:
        return False
    if not isinstance(value[name], dict):
        return False
    return set(value) <= {name, "target", "_metadata"}


def _validate_aliases(value: list[str] | str | None, field: str) -> None:
    if value is None:
        return
    items = [value] if isinstance(value, str) else list(value)
    if any(not str(item).strip() for item in items):
        raise ValueError(f"{field} cannot contain empty values")


def _validate_tags(value: dict[str, Any], field: str) -> None:
    for key, item in value.items():
        if not str(key).strip() or not str(item).strip():
            raise ValueError(f"{field} cannot contain empty keys or values")
