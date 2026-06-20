"""Pydantic quality rule contract models."""

from __future__ import annotations

from typing import Any

from pydantic import Field, ValidationError, field_validator

from contractforge_core.config import QualityRuleSeverity, VALID_QUALITY_RULE_SEVERITIES
from contractforge_core.contracts.base import ExtensibleContractModel, StrictContractModel, contract_validation_error


class QualityExpressionContractModel(StrictContractModel):
    name: str
    expression: str
    severity: QualityRuleSeverity = "quarantine"
    message: str | None = None

    @field_validator("name", "expression")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, value: str) -> str:
        if value not in VALID_QUALITY_RULE_SEVERITIES:
            raise ValueError(f"must be one of {sorted(VALID_QUALITY_RULE_SEVERITIES)}")
        return value


class QualityCustomRuleContractModel(ExtensibleContractModel):
    type: str
    severity: QualityRuleSeverity = "abort"
    message: str | None = None

    @field_validator("type")
    @classmethod
    def _type_required(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value


class QualityRulesContractModel(StrictContractModel):
    required_columns: list[str] | str | None = None
    not_null: list[str] | str | None = None
    unique_key: list[str] | str | None = None
    accepted_values: dict[str, list[Any] | str | int | float | bool | None] = Field(default_factory=dict)
    min_rows: int | None = Field(default=None, gt=0)
    max_null_ratio: dict[str, float] = Field(default_factory=dict)
    expressions: list[QualityExpressionContractModel] = Field(default_factory=list)
    custom: dict[str, QualityCustomRuleContractModel] = Field(default_factory=dict)

    @field_validator("required_columns", "not_null", "unique_key", mode="before")
    @classmethod
    def _column_names_must_not_be_empty(cls, value: Any) -> Any:
        if value is None:
            return value
        values = [value] if isinstance(value, str) else list(value)
        if not values or any(not str(item).strip() for item in values):
            raise ValueError("column names must not be empty")
        return value

    @field_validator("accepted_values")
    @classmethod
    def _accepted_value_columns(cls, value: dict[str, Any]) -> dict[str, Any]:
        for column in value:
            if not str(column).strip():
                raise ValueError("cannot contain empty column names")
        return value

    @field_validator("max_null_ratio")
    @classmethod
    def _ratios(cls, value: dict[str, float]) -> dict[str, float]:
        for column, ratio in value.items():
            if not str(column).strip():
                raise ValueError("cannot contain empty column names")
            if ratio < 0 or ratio > 1:
                raise ValueError("ratios must be between 0 and 1")
        return value

    @field_validator("expressions")
    @classmethod
    def _unique_expression_names(
        cls,
        value: list[QualityExpressionContractModel],
    ) -> list[QualityExpressionContractModel]:
        names = [rule.name for rule in value]
        if len(names) != len(set(names)):
            raise ValueError("expression names must be unique")
        return value

    @field_validator("custom")
    @classmethod
    def _custom_names(cls, value: dict[str, QualityCustomRuleContractModel]) -> dict[str, QualityCustomRuleContractModel]:
        for name in value:
            if not str(name).strip():
                raise ValueError("custom rule names must not be empty")
        return value


def validate_quality_rules_contract(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("quality_rules must be an object")
    try:
        return QualityRulesContractModel.model_validate(value).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="quality_rules") from exc
