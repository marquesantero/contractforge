"""Typed state models for intent-first project synthesis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_ai.models import EvidenceItem, RequiredDecision

Layer = Literal["bronze", "silver", "gold"]
GapActionType = Literal["generate", "preserve", "patch"]
TransformationAction = Literal["select", "rename", "cast", "review_required"]


@dataclass(frozen=True)
class IntentSpec:
    """Normalized representation of a free-form project generation request."""

    prompt: str
    requested_layers: list[Layer]
    source: str | None
    target_table: str | None
    base_name: str
    catalog: str
    final_columns: list[str] = field(default_factory=list)
    hash_columns: list[str] = field(default_factory=list)
    quality_rules: dict[str, Any] = field(default_factory=dict)
    operations: dict[str, Any] = field(default_factory=dict)
    dab_compute: dict[str, Any] = field(default_factory=dict)
    schedule: dict[str, Any] = field(default_factory=dict)
    platform_hints: list[str] = field(default_factory=list)
    silver_mode: str = "hash_diff_upsert"
    output_target: str = "contractforge-yaml"
    completion_goal: str = "generate_requested_layers"
    decisions_required: list[RequiredDecision] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    confidence: float = 0.70

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "requested_layers": self.requested_layers,
            "source": self.source,
            "target_table": self.target_table,
            "base_name": self.base_name,
            "catalog": self.catalog,
            "final_columns": self.final_columns,
            "hash_columns": self.hash_columns,
            "quality_rules": self.quality_rules,
            "operations": self.operations,
            "dab_compute": self.dab_compute,
            "schedule": self.schedule,
            "platform_hints": self.platform_hints,
            "silver_mode": self.silver_mode,
            "output_target": self.output_target,
            "completion_goal": self.completion_goal,
            "decisions_required": [item.to_dict() for item in self.decisions_required],
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ContractSummary:
    """Summary of an existing ContractForge contract."""

    path: str
    layer: Layer | None
    target_catalog: str | None
    target_schema: str | None
    target_table: str | None
    mode: str | None
    source_connector: str | None
    source_table: str | None
    source_path: str | None
    has_annotations: bool = False
    has_operations: bool = False

    @property
    def full_target_name(self) -> str | None:
        if self.target_catalog and self.target_schema and self.target_table:
            return f"{self.target_catalog}.{self.target_schema}.{self.target_table}"
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "layer": self.layer,
            "target_catalog": self.target_catalog,
            "target_schema": self.target_schema,
            "target_table": self.target_table,
            "mode": self.mode,
            "source_connector": self.source_connector,
            "source_table": self.source_table,
            "source_path": self.source_path,
            "has_annotations": self.has_annotations,
            "has_operations": self.has_operations,
        }


@dataclass(frozen=True)
class ProjectState:
    """Current state discovered from an existing ContractForge project directory."""

    root: str | None
    contracts: list[ContractSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def layers(self) -> list[Layer]:
        found: list[Layer] = []
        for layer in ("bronze", "silver", "gold"):
            if any(contract.layer == layer for contract in self.contracts):
                found.append(layer)
        return found

    def contract_for_layer(self, layer: Layer) -> ContractSummary | None:
        for contract in self.contracts:
            if contract.layer == layer:
                return contract
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "layers": self.layers,
            "contracts": [contract.to_dict() for contract in self.contracts],
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class GapAction:
    """One ordered action required to reach the desired project state."""

    action: GapActionType
    layer: Layer
    reason: str
    existing_contract: str | None = None
    source_table: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "layer": self.layer,
            "reason": self.reason,
            "existing_contract": self.existing_contract,
            "source_table": self.source_table,
        }


@dataclass(frozen=True)
class GapPlan:
    """Ordered plan for preserving, generating or patching artifacts."""

    actions: list[GapAction]
    decisions_required: list[RequiredDecision] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def layers_to_generate(self) -> list[Layer]:
        return [action.layer for action in self.actions if action.action == "generate"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions": [action.to_dict() for action in self.actions],
            "layers_to_generate": self.layers_to_generate,
            "decisions_required": [item.to_dict() for item in self.decisions_required],
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class TransformationStep:
    """One inferred or review-required transformation step."""

    action: TransformationAction
    column: str
    expression: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "column": self.column,
            "expression": self.expression,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TransformationPlan:
    """Evidence-bound transformation plan for generated contracts."""

    steps: list[TransformationStep] = field(default_factory=list)
    transform: dict[str, Any] = field(default_factory=dict)
    decisions_required: list[RequiredDecision] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def shape_columns(self) -> dict[str, str]:
        return {
            step.column: step.expression
            for step in self.steps
            if step.action in {"select", "rename", "cast"} and step.expression
        }

    @property
    def contract_transform(self) -> dict[str, Any]:
        payload = _deep_merge({}, self.transform)
        if self.shape_columns:
            shape = _deep_merge(payload.get("shape") if isinstance(payload.get("shape"), dict) else {}, {"columns": self.shape_columns})
            payload["shape"] = shape
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "shape_columns": self.shape_columns,
            "transform": self.contract_transform,
            "decisions_required": [item.to_dict() for item in self.decisions_required],
            "warnings": self.warnings,
        }


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
