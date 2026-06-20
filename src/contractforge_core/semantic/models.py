"""Immutable semantic ingestion intent models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Literal

WriteMode = str
SchemaPolicy = Literal["permissive", "additive_only", "strict"]
HashStrategy = Literal["explicit", "all_columns_except"]
SCD2LateArrivingPolicy = Literal["apply", "ignore", "reject"]
QualityRuleKind = Literal[
    "required_columns",
    "not_null",
    "unique_key",
    "accepted_values",
    "row_count_minimum",
    "max_null_ratio",
    "expression",
]


@dataclass(frozen=True)
class SourceIntent:
    name: str
    kind: str
    location: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class TargetIntent:
    name: str
    layer: str
    namespace: str | None = None
    domain: str | None = None
    catalog_type: str | None = None


@dataclass(frozen=True)
class WriteIntent:
    mode: WriteMode
    schema_policy: SchemaPolicy = "permissive"
    merge_keys: tuple[str, ...] = ()
    hash_strategy: HashStrategy = "explicit"
    hash_keys: tuple[str, ...] = ()
    hash_exclude_columns: tuple[str, ...] = ()
    scd2_change_columns: tuple[str, ...] = ()
    scd2_effective_from_column: str | None = None
    scd2_sequence_by: str | None = None
    scd2_late_arriving_policy: SCD2LateArrivingPolicy = "apply"
    scd2_apply_as_deletes: str | None = None


@dataclass(frozen=True)
class QualityIntent:
    name: str
    rule: QualityRuleKind
    columns: tuple[str, ...] = ()
    value: object | None = None
    severity: str = "quarantine"
    message: str | None = None


@dataclass(frozen=True)
class GovernanceIntent:
    owner: str | None = None
    row_filters: tuple[str, ...] = ()
    column_masks: tuple[str, ...] = ()
    access: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None


@dataclass(frozen=True)
class OperationsIntent:
    available_now_streaming: bool = False
    require_production_evidence: bool = True
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ShapeIntent:
    raw: dict[str, Any]


@dataclass(frozen=True)
class TransformIntent:
    raw: dict[str, Any]


@dataclass(frozen=True)
class NamingIntent:
    raw: dict[str, Any]


@dataclass(frozen=True)
class SemanticContract:
    source: SourceIntent
    target: TargetIntent
    write: WriteIntent
    quality: tuple[QualityIntent, ...] = ()
    governance: GovernanceIntent | None = None
    operations: OperationsIntent | None = None
    shape: ShapeIntent | None = None
    transform: TransformIntent | None = None
    naming: NamingIntent | None = None
    extensions: dict[str, Any] | None = None
