"""Root ContractForge-style contract model for platform-neutral validation."""

from __future__ import annotations

import re
from typing import Any

from pydantic import Field, ValidationError, field_validator, model_validator

from contractforge_core.config import (
    PUBLIC_WRITE_MODES,
    VALID_IDEMPOTENCY_POLICIES,
    VALID_QUALITY_FAIL_ACTIONS,
    VALID_SCD2_LATE_ARRIVING_POLICIES,
    VALID_SCHEMA_POLICIES,
    canonical_write_mode,
    is_valid_write_mode,
)
from contractforge_core.contracts.base import StrictContractModel, contract_validation_error
from contractforge_core.contracts.execution import ExecutionContractModel
from contractforge_core.contracts.governance import (
    AccessContractModel,
    AnnotationsContractModel,
    OperationsContractModel,
)
from contractforge_core.contracts.quality import QualityRulesContractModel
from contractforge_core.contracts.source import ConnectorSourceContract, GenericSourceContract
from contractforge_core.contracts.transform import ShapeContractModel, TransformContractModel

_LAYER_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class TargetContractModel(StrictContractModel):
    catalog: str | None = None
    catalog_type: str | None = None
    schema_: str | None = Field(default=None, alias="schema")
    table: str | None = None


class SemanticContractInputModel(StrictContractModel):
    """Validated external contract shape accepted by the core.

    This is intentionally broad enough to accept ContractForge contracts while
    keeping platform execution fields out of the semantic core.
    """

    source: str | ConnectorSourceContract | GenericSourceContract
    target: TargetContractModel
    layer: str = "bronze"
    mode: str = "append"
    schema_policy: str = "permissive"
    owner: str | None = None
    domain: str | None = None
    naming: dict[str, Any] | None = None
    tags: list[str] | str | None = None
    sla: str | None = None
    runtime_parameters: dict[str, Any] | None = None
    description: str | None = None
    schemas: dict[str, str] | None = None
    quality_rules: QualityRulesContractModel | None = None
    on_quality_fail: str = "fail"
    select_columns: list[str] | str | None = None
    column_mapping: dict[str, str] | None = None
    filter_expression: str | None = None
    watermark_columns: list[str] | str | None = None
    merge_keys: list[str] | str | None = None
    hash_strategy: str = "explicit"
    hash_keys: list[str] | str | None = None
    hash_exclude_columns: list[str] | str | None = None
    scd2_change_columns: list[str] | str | None = None
    scd2_effective_from_column: str | None = None
    scd2_sequence_by: str | None = None
    scd2_late_arriving_policy: str = "apply"
    scd2_apply_as_deletes: str | None = None
    shape: ShapeContractModel | None = None
    transform: TransformContractModel | None = None
    annotations: AnnotationsContractModel | None = None
    operations: OperationsContractModel | None = None
    access: AccessContractModel | None = None
    execution: ExecutionContractModel | None = None
    idempotency_key: str | None = None
    idempotency_policy: str = "always_run"
    retry_attempts: int | None = Field(default=None, ge=1)
    retry_backoff_seconds: int | None = Field(default=None, ge=0)
    applied_presets: list[str] | str | None = None
    parent_run_id: str | None = None
    run_group_id: str | None = None
    master_job_id: str | None = None
    master_run_id: str | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False

    @field_validator("mode")
    @classmethod
    def _valid_mode(cls, value: str) -> str:
        if not is_valid_write_mode(value):
            raise ValueError(f"must be one of {sorted(PUBLIC_WRITE_MODES)} or custom:<name>")
        return canonical_write_mode(value)

    @field_validator("layer")
    @classmethod
    def _valid_layer(cls, value: str) -> str:
        if not _LAYER_NAME_RE.match(value):
            raise ValueError("must start with a letter and contain only letters, numbers, '_' or '-'")
        return value

    @field_validator("schema_policy")
    @classmethod
    def _valid_schema_policy(cls, value: str) -> str:
        if value not in VALID_SCHEMA_POLICIES:
            raise ValueError(f"must be one of {sorted(VALID_SCHEMA_POLICIES)}")
        return value

    @field_validator("hash_strategy")
    @classmethod
    def _valid_hash_strategy(cls, value: str) -> str:
        if value not in {"explicit", "all_columns_except"}:
            raise ValueError("must be one of ['all_columns_except', 'explicit']")
        return value

    @field_validator("on_quality_fail")
    @classmethod
    def _valid_on_quality_fail(cls, value: str) -> str:
        if value not in VALID_QUALITY_FAIL_ACTIONS:
            raise ValueError(f"must be one of {sorted(VALID_QUALITY_FAIL_ACTIONS)}")
        return value

    @field_validator("scd2_late_arriving_policy")
    @classmethod
    def _valid_scd2_late_arriving_policy(cls, value: str) -> str:
        if value not in VALID_SCD2_LATE_ARRIVING_POLICIES:
            raise ValueError(f"must be one of {sorted(VALID_SCD2_LATE_ARRIVING_POLICIES)}")
        return value

    @field_validator("idempotency_policy")
    @classmethod
    def _valid_idempotency_policy(cls, value: str) -> str:
        if value not in VALID_IDEMPOTENCY_POLICIES:
            raise ValueError(f"must be one of {sorted(VALID_IDEMPOTENCY_POLICIES)}")
        return value

    @model_validator(mode="after")
    def _target_required(self) -> "SemanticContractInputModel":
        if self.target and self.target.table:
            return self
        raise ValueError("target.table is required")


_LEGACY_CONTRACT_HINTS = {
    "target_table": "Move it under target.table (declare target: {catalog, schema, table}).",
    "target_schema": "Move it under target.schema.",
    "catalog": "Move it under target.catalog.",
    "ctrl_schema": "Evidence schema is owned by the runtime; pass it through adapter runtime options.",
    "source_system": "Declare it under source.system inside the source block.",
    "dedup_order_expr": "Use transform.deduplicate.order_by with explicit column entries.",
    "delta_properties": "Move platform-specific table properties under the responsible adapter extension namespace.",
    "cluster_columns": "Move platform-specific clustering fields under the responsible adapter extension namespace.",
    "partition_columns": "Move platform-specific physical partitioning fields under the responsible adapter extension namespace.",
}


def _reject_legacy_top_level_fields(contract: dict[str, Any]) -> None:
    legacy = [name for name in _LEGACY_CONTRACT_HINTS if name in contract]
    if not legacy:
        return
    hints = "; ".join(f"{name}: {_LEGACY_CONTRACT_HINTS[name]}" for name in legacy)
    raise ValueError(
        f"contract declares legacy top-level field(s) no longer accepted: {sorted(legacy)}. {hints}"
    )


def validate_contract(value: Any) -> dict[str, Any]:
    """Validate a root contract and return a normalized mapping."""
    if not isinstance(value, dict):
        raise ValueError("contract must be an object")
    _reject_legacy_top_level_fields(value)
    try:
        return SemanticContractInputModel.model_validate(value).model_dump(exclude_none=True, by_alias=True)
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="contract") from exc
