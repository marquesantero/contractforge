"""Pydantic shape and transform contract models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator

from contractforge_core.config import ARRAY_MODES
from contractforge_core.contracts.base import StrictContractModel, contract_validation_error
from contractforge_core.contracts.shape_validation import validate_shape_semantics

ArrayMode = Literal["keep", "to_json", "size", "first", "explode", "explode_outer"]


class ShapeJsonContractModel(StrictContractModel):
    column: str
    schema_: str | None = Field(default=None, alias="schema")
    schema_ref: str | None = None
    alias: str | None = None
    drop_source: bool = False
    cast_input: str | None = None

    @field_validator("column")
    @classmethod
    def _column_required(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("cast_input")
    @classmethod
    def _cast_input_supported(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip().upper()
        if normalized != "STRING":
            raise ValueError("cast_input currently supports STRING only")
        return normalized


class ShapeFlattenContractModel(StrictContractModel):
    enabled: bool = False
    separator: str = "_"
    include: list[str] | str | None = None
    exclude: list[str] | str | None = None
    max_depth: int = Field(default=10, gt=0)


class ShapeZipArraysContractModel(StrictContractModel):
    alias: str
    columns: dict[str, str]


class ShapeArrayContractModel(StrictContractModel):
    path: str
    mode: ArrayMode = "keep"
    alias: str | None = None
    allow_cartesian: bool = False

    @field_validator("mode")
    @classmethod
    def _valid_mode(cls, value: str) -> str:
        if value not in ARRAY_MODES:
            raise ValueError(f"must be one of {sorted(ARRAY_MODES)}")
        return value


class ShapeColumnContractModel(StrictContractModel):
    alias: str | None = None
    cast: str | None = None
    expression: str | None = None


class ShapeContractModel(StrictContractModel):
    parse_json: list[ShapeJsonContractModel] | None = None
    flatten: ShapeFlattenContractModel | bool | None = None
    zip_arrays: list[ShapeZipArraysContractModel] | None = None
    arrays: list[ShapeArrayContractModel] | None = None
    columns: dict[str, ShapeColumnContractModel | str] | None = None
    allow_cardinality_change_on_bronze: bool = False

    @field_validator("parse_json", "zip_arrays", "arrays", mode="before")
    @classmethod
    def _must_be_list(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, (dict, str)):
            raise ValueError("must be a list")
        return value


class StandardizeColumnContractModel(StrictContractModel):
    trim: bool = False
    lower: bool = False
    upper: bool = False
    normalize_whitespace: bool = False
    empty_as_null: bool = False

    @field_validator("upper")
    @classmethod
    def _reject_lower_and_upper(cls, value: bool, info: Any) -> bool:
        if value and info.data.get("lower"):
            raise ValueError("cannot be true when lower is true")
        return value


class DeduplicateOrderContractModel(StrictContractModel):
    column: str
    direction: Literal["asc", "desc"] = "desc"
    nulls: Literal["first", "last"] | None = None


class DeduplicateContractModel(StrictContractModel):
    keys: list[str] | str
    order_by: str | list[DeduplicateOrderContractModel]


class CustomTransformContractModel(StrictContractModel):
    """Portable custom treatment declaration; runtime bindings live in adapter extensions."""

    name: str | None = None
    description: str | None = None
    output: str | None = None
    expected_columns: list[str] | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("expected_columns", mode="before")
    @classmethod
    def _expected_columns_must_be_list(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            raise ValueError("must be a list")
        return value


class TransformContractModel(StrictContractModel):
    shape: ShapeContractModel | None = None
    cast: dict[str, str] | None = None
    composite_keys: dict[str, list[str] | str] | None = None
    derive: dict[str, str] | None = None
    standardize: dict[str, StandardizeColumnContractModel] | None = None
    deduplicate: DeduplicateContractModel | None = None
    custom: CustomTransformContractModel | None = None

    @field_validator("cast", "derive", mode="before")
    @classmethod
    def _mapping_values_must_be_text(cls, value: Any) -> Any:
        if value is None:
            return value
        if not isinstance(value, dict):
            raise ValueError("must be an object/dict")
        for key, item in value.items():
            if not str(key).strip() or not str(item or "").strip():
                raise ValueError("cannot contain empty keys or values")
        return value

    @field_validator("composite_keys", mode="before")
    @classmethod
    def _composite_keys_must_have_sources(cls, value: Any) -> Any:
        if value is None:
            return value
        if not isinstance(value, dict):
            raise ValueError("must be an object/dict")
        for key, item in value.items():
            if not str(key).strip():
                raise ValueError("cannot contain empty keys")
            columns = [item] if isinstance(item, str) else list(item or ())
            if not columns or any(not str(column).strip() for column in columns):
                raise ValueError("composite key source columns must not be empty")
        return value


def validate_shape_contract(value: Any) -> dict[str, Any]:
    if value is None or not isinstance(value, dict):
        return value
    try:
        shape = ShapeContractModel.model_validate(value).model_dump(exclude_none=True, by_alias=True)
        validate_shape_semantics(shape)
        return shape
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="shape") from exc


def validate_transform_contract(value: Any) -> dict[str, Any]:
    if value is None or not isinstance(value, dict):
        return value
    try:
        transform = TransformContractModel.model_validate(value).model_dump(exclude_none=True, by_alias=True)
        validate_shape_semantics(transform.get("shape"), context="transform.shape")
        return transform
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="transform") from exc
