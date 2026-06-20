"""Lakeflow AUTO CDC compatibility checks for semantic contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.rendering.names import target_full_name

LakeflowStatus = Literal["compatible", "requires_translation", "unsupported"]
LakeflowSourceKind = Literal["change_feed", "snapshot"]


@dataclass(frozen=True)
class LakeflowCompatibility:
    status: LakeflowStatus
    source_kind: LakeflowSourceKind
    scd_type: int | None
    target_table: str
    reasons: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    mapped_fields: dict[str, Any] | None = None
    translation_required: tuple[str, ...] = ()
    unsupported_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.status != "unsupported"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "supported": self.supported,
            "source_kind": self.source_kind,
            "scd_type": self.scd_type,
            "target_table": self.target_table,
            "reasons": list(self.reasons),
            "required_fields": list(self.required_fields),
            "mapped_fields": dict(self.mapped_fields or {}),
            "translation_required": list(self.translation_required),
            "unsupported_fields": list(self.unsupported_fields),
            "warnings": list(self.warnings),
        }


def evaluate_lakeflow_compatibility(
    contract: SemanticContract,
    *,
    source_kind: LakeflowSourceKind = "change_feed",
    source_name: str | None = None,
    keys: tuple[str, ...] = (),
    sequence_by: str | None = None,
    apply_as_truncates: str | None = None,
) -> LakeflowCompatibility:
    reasons: list[str] = []
    required: list[str] = []
    translation: list[str] = []
    unsupported: list[str] = []
    warnings: list[str] = []
    scd_type = _scd_type(contract.write.mode)
    target_table = target_full_name(contract)
    effective_keys = keys or contract.write.merge_keys
    effective_sequence_by = sequence_by or contract.write.scd2_sequence_by
    mapped_fields: dict[str, Any] = {
        "target": target_table,
        "source": source_name,
        "keys": list(effective_keys),
        "sequence_by": effective_sequence_by,
        "stored_as_scd_type": scd_type,
        "apply_as_deletes": contract.write.scd2_apply_as_deletes,
        "apply_as_truncates": apply_as_truncates,
    }

    if scd_type is None:
        unsupported.append("mode")
        reasons.append(f"{contract.write.mode} does not map directly to Lakeflow AUTO CDC.")
    if not source_name:
        required.append("source_name")
        reasons.append("Lakeflow AUTO CDC requires a source table, view, or snapshot function.")
    if not effective_keys:
        required.append("keys")
        reasons.append("Lakeflow AUTO CDC requires stable keys.")
    if source_kind not in {"change_feed", "snapshot"}:
        unsupported.append("source_kind")
        reasons.append("Lakeflow source_kind must be 'change_feed' or 'snapshot'.")
    if source_kind == "change_feed" and scd_type == 2 and not effective_sequence_by:
        required.append("sequence_by")
        reasons.append("Lakeflow AUTO CDC SCD2 requires sequence_by.")
    if source_kind == "snapshot" and contract.write.scd2_apply_as_deletes:
        unsupported.append("apply_as_deletes")
        reasons.append("AUTO CDC FROM SNAPSHOT derives deletes from snapshots and does not use CDC delete predicates.")
    if apply_as_truncates and scd_type == 2:
        unsupported.append("apply_as_truncates")
        reasons.append("Lakeflow apply_as_truncates is supported only for SCD type 1.")
    if scd_type == 2 and contract.write.scd2_change_columns:
        mapped_fields["track_history_column_list"] = list(contract.write.scd2_change_columns)
    elif scd_type == 2:
        warnings.append("SCD2 without scd2_change_columns maps to Lakeflow's default of tracking all output columns.")
    if contract.quality:
        translation.append("quality")
        reasons.append("Quality rules must be materialized upstream or enforced outside AUTO CDC.")
    metadata = contract.operations.metadata if contract.operations and contract.operations.metadata else {}
    _translation_from_metadata(
        metadata,
        translation,
        reasons,
        "select_columns",
        "Projection intent must be materialized upstream as the Lakeflow source table/view.",
    )
    _translation_from_metadata(
        metadata,
        translation,
        reasons,
        "column_mapping",
        "Column mapping intent must be materialized upstream as the Lakeflow source table/view.",
    )
    _translation_from_metadata(
        metadata,
        translation,
        reasons,
        "filter_expression",
        "Filter intent must be materialized upstream as the Lakeflow source table/view.",
    )
    _translation_from_metadata(
        metadata,
        translation,
        reasons,
        "watermark_columns",
        "Watermark filtering/state remains ContractForge runtime behavior and must be resolved before AUTO CDC.",
    )
    if contract.shape:
        translation.append("shape")
        reasons.append("Shape intent must be materialized upstream as the Lakeflow source table/view.")
    if contract.transform:
        translation.append("transform")
        reasons.append("Transform intent must be materialized upstream as the Lakeflow source table/view.")

    if unsupported or required:
        status: LakeflowStatus = "unsupported"
    elif translation:
        status = "requires_translation"
    else:
        status = "compatible"
        reasons.append("Contract can map to Lakeflow AUTO CDC arguments.")

    return LakeflowCompatibility(
        status=status,
        source_kind=source_kind,
        scd_type=scd_type,
        target_table=target_table,
        reasons=tuple(reasons),
        required_fields=tuple(required),
        mapped_fields={key: value for key, value in mapped_fields.items() if value is not None},
        translation_required=tuple(translation),
        unsupported_fields=tuple(unsupported),
        warnings=tuple(warnings),
    )


def render_lakeflow_review(compatibility: LakeflowCompatibility) -> str:
    lines = [
        "# Lakeflow AUTO CDC Compatibility",
        "",
        f"- Status: `{compatibility.status}`",
        f"- SCD type: `{compatibility.scd_type}`",
        "",
    ]
    for reason in compatibility.reasons:
        lines.append(f"- {reason}")
    for warning in compatibility.warnings:
        lines.append(f"- Warning: {warning}")
    return "\n".join(lines) + "\n"


def _scd_type(mode: str) -> int | None:
    if mode == "scd1_upsert":
        return 1
    if mode == "scd2_historical":
        return 2
    return None


def _translation_from_metadata(
    metadata: dict[str, Any],
    translation: list[str],
    reasons: list[str],
    key: str,
    reason: str,
) -> None:
    if metadata.get(key) not in (None, "", [], {}):
        translation.append(key)
        reasons.append(reason)
