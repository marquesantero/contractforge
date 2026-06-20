"""Environment contract for adapter execution context."""

from __future__ import annotations

from typing import Any

from pydantic import Field, ValidationError, field_validator, model_validator

from contractforge_core.contracts.base import ExtensibleContractModel, StrictContractModel, contract_validation_error

_FORBIDDEN_SEMANTIC_FIELDS = {
    "access",
    "annotations",
    "layer",
    "merge_keys",
    "mode",
    "operations",
    "quality_rules",
    "schema_policy",
    "source",
    "target",
    "target_table",
    "transform",
}


class EnvironmentMap(ExtensibleContractModel):
    """Opaque environment subsection interpreted by adapters."""


class EnvironmentCapabilitiesContractModel(StrictContractModel):
    require: list[str] | str | None = None
    prefer: list[str] | str | None = None
    forbid: list[str] | str | None = None


class EnvironmentContractModel(StrictContractModel):
    name: str = "dev"
    adapter: str
    runtime: EnvironmentMap = Field(default_factory=EnvironmentMap)
    deployment: EnvironmentMap = Field(default_factory=EnvironmentMap)
    artifacts: EnvironmentMap = Field(default_factory=EnvironmentMap)
    evidence: EnvironmentMap = Field(default_factory=EnvironmentMap)
    secrets: EnvironmentMap = Field(default_factory=EnvironmentMap)
    defaults: EnvironmentMap = Field(default_factory=EnvironmentMap)
    capabilities: EnvironmentCapabilitiesContractModel = Field(default_factory=EnvironmentCapabilitiesContractModel)
    parameters: dict[str, EnvironmentMap] = Field(default_factory=dict)

    @field_validator("name", "adapter")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="before")
    @classmethod
    def _reject_semantic_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        raw = _unwrap_environment(value)
        forbidden = sorted(_FORBIDDEN_SEMANTIC_FIELDS & set(raw))
        if forbidden:
            raise ValueError(f"environment cannot contain semantic contract fields: {forbidden}")
        return raw


def validate_environment_contract(value: Any) -> dict[str, Any]:
    """Validate an environment contract and return a normalized mapping."""
    if value is None or not isinstance(value, dict):
        return value
    try:
        return EnvironmentContractModel.model_validate(value).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="environment") from exc


def _unwrap_environment(value: dict[str, Any]) -> dict[str, Any]:
    nested = value.get("environment")
    return dict(nested) if isinstance(nested, dict) else value
