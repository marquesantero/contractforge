"""Lakeflow AUTO CDC Python artifact rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.lakeflow.compatibility import (
    LakeflowCompatibility,
    LakeflowSourceKind,
    evaluate_lakeflow_compatibility,
)
from contractforge_databricks.rendering.names import target_full_name


@dataclass(frozen=True)
class LakeflowAutoCdcArtifact:
    language: Literal["python"]
    source_kind: LakeflowSourceKind
    code: str
    compatibility: LakeflowCompatibility

    def as_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "source_kind": self.source_kind,
            "code": self.code,
            "compatibility": self.compatibility.as_dict(),
        }


def render_lakeflow_auto_cdc_python(
    contract: SemanticContract,
    *,
    source_kind: LakeflowSourceKind = "change_feed",
    source_name: str,
    keys: tuple[str, ...] = (),
    sequence_by: str | None = None,
    flow_name: str | None = None,
    apply_as_truncates: str | None = None,
    ignore_null_updates: bool = False,
    once: bool = False,
) -> str:
    return render_lakeflow_auto_cdc_artifact(
        contract,
        source_kind=source_kind,
        source_name=source_name,
        keys=keys,
        sequence_by=sequence_by,
        flow_name=flow_name,
        apply_as_truncates=apply_as_truncates,
        ignore_null_updates=ignore_null_updates,
        once=once,
    ).code


def render_lakeflow_auto_cdc_artifact(
    contract: SemanticContract,
    *,
    source_kind: LakeflowSourceKind = "change_feed",
    source_name: str,
    keys: tuple[str, ...] = (),
    sequence_by: str | None = None,
    flow_name: str | None = None,
    apply_as_truncates: str | None = None,
    ignore_null_updates: bool = False,
    once: bool = False,
) -> LakeflowAutoCdcArtifact:
    compatibility = evaluate_lakeflow_compatibility(
        contract,
        source_kind=source_kind,
        source_name=source_name,
        keys=keys,
        sequence_by=sequence_by,
        apply_as_truncates=apply_as_truncates,
    )
    if compatibility.status == "unsupported":
        raise ValueError("; ".join(compatibility.reasons))

    if source_kind == "snapshot":
        code = _render_snapshot_flow(
            contract,
            source_name=source_name,
            keys=keys or contract.write.merge_keys,
            flow_name=flow_name,
            scd_type=compatibility.scd_type,
        )
    else:
        code = _render_change_feed_flow(
            contract,
            source_name=source_name,
            keys=keys or contract.write.merge_keys,
            sequence_by=sequence_by or contract.write.scd2_sequence_by,
            flow_name=flow_name,
            scd_type=compatibility.scd_type,
            apply_as_truncates=apply_as_truncates,
            ignore_null_updates=ignore_null_updates,
            once=once,
        )
    return LakeflowAutoCdcArtifact(
        language="python",
        source_kind=source_kind,
        code=code,
        compatibility=compatibility,
    )


def _render_change_feed_flow(
    contract: SemanticContract,
    *,
    source_name: str,
    keys: tuple[str, ...],
    sequence_by: str | None,
    flow_name: str | None,
    scd_type: int | None,
    apply_as_truncates: str | None,
    ignore_null_updates: bool,
    once: bool,
) -> str:
    target = target_full_name(contract)
    lines = [
        "from pyspark import pipelines as dp",
        "",
        f"dp.create_streaming_table(name={target!r})",
        "",
        "dp.create_auto_cdc_flow(",
        f"    target={target!r},",
        f"    source={source_name!r},",
        f"    keys={list(keys)!r},",
        f"    stored_as_scd_type={scd_type!r},",
        f"    ignore_null_updates={ignore_null_updates!r},",
    ]
    if sequence_by:
        lines.append(f"    sequence_by={sequence_by!r},")
    if contract.write.scd2_apply_as_deletes:
        lines.append(f"    apply_as_deletes={contract.write.scd2_apply_as_deletes!r},")
    if apply_as_truncates:
        lines.append(f"    apply_as_truncates={apply_as_truncates!r},")
    if contract.write.scd2_change_columns:
        lines.append(f"    track_history_column_list={list(contract.write.scd2_change_columns)!r},")
    if flow_name:
        lines.append(f"    name={flow_name!r},")
    if once:
        lines.append("    once=True,")
    lines.append(")")
    return "\n".join(lines) + "\n"


def _render_snapshot_flow(
    contract: SemanticContract,
    *,
    source_name: str,
    keys: tuple[str, ...],
    flow_name: str | None,
    scd_type: int | None,
) -> str:
    target = target_full_name(contract)
    lines = [
        "from pyspark import pipelines as dp",
        "",
        f"dp.create_streaming_table(name={target!r})",
        "",
        "dp.create_auto_cdc_from_snapshot_flow(",
        f"    target={target!r},",
        f"    source={source_name!r},",
        f"    keys={list(keys)!r},",
        f"    stored_as_scd_type={scd_type!r},",
    ]
    if contract.write.scd2_change_columns:
        lines.append(f"    track_history_column_list={list(contract.write.scd2_change_columns)!r},")
    if flow_name:
        lines.append(f"    name={flow_name!r},")
    lines.append(")")
    return "\n".join(lines) + "\n"
