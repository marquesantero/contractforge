"""Planner checks for write, schema and evidence semantics."""

from __future__ import annotations

from contractforge_core.capabilities.models import PlatformCapabilities
from contractforge_core.planner.result import PlanningBlocker, PlanningWarning
from contractforge_core.semantic.models import SemanticContract


def match_write_mode(
    contract: SemanticContract,
    capabilities: PlatformCapabilities,
    blockers: list[PlanningBlocker],
    review_markers: list[str],
) -> None:
    mode = contract.write.mode
    _validate_write_semantics(contract, blockers)
    if blockers:
        return
    review_required = set(capabilities.review_required_semantics)
    if mode in review_required:
        review_markers.append(mode)
        return

    if mode == "scd0_append" and not capabilities.supports_append:
        blockers.append(PlanningBlocker("APPEND_UNSUPPORTED", "Append writes are not supported."))
    elif mode == "scd0_overwrite" and not capabilities.supports_overwrite:
        blockers.append(PlanningBlocker("OVERWRITE_UNSUPPORTED", "Overwrite writes are not supported."))
    elif mode == "scd1_upsert" and not capabilities.supports_merge:
        blockers.append(PlanningBlocker("MERGE_UNSUPPORTED", "SCD1 upsert requires merge capability."))
    elif mode == "scd1_hash_diff":
        _match_hash_diff(capabilities, blockers)
    elif mode == "scd2_historical":
        _match_scd2(capabilities, blockers)
    elif mode == "snapshot_soft_delete" and not capabilities.supports_snapshot_soft_delete:
        blockers.append(
            PlanningBlocker(
                "SNAPSHOT_SOFT_DELETE_UNSUPPORTED",
                "Snapshot soft delete requires adapter-declared snapshot reconciliation capability.",
            )
        )
    elif mode.startswith("custom:") and mode not in capabilities.supported_custom_write_modes:
        review_markers.append(mode)
    elif mode not in capabilities.supported_custom_write_modes and mode not in {
        "scd0_append",
        "scd0_overwrite",
        "scd1_upsert",
        "scd1_hash_diff",
        "scd2_historical",
        "snapshot_soft_delete",
    }:
        blockers.append(PlanningBlocker("WRITE_MODE_UNSUPPORTED", f"Unsupported write mode: {mode}."))


def match_schema_policy(
    contract: SemanticContract,
    capabilities: PlatformCapabilities,
    warnings: list[PlanningWarning],
) -> None:
    if contract.write.schema_policy == "additive_only" and not capabilities.supports_schema_evolution:
        warnings.append(
            PlanningWarning(
                "SCHEMA_EVOLUTION_UNAVAILABLE",
                "Additive schema policy requires adapter-managed schema evolution.",
            )
        )


def match_evidence(
    contract: SemanticContract,
    capabilities: PlatformCapabilities,
    blockers: list[PlanningBlocker],
) -> None:
    operations = contract.operations
    evidence_required = True if operations is None else operations.require_production_evidence
    if evidence_required and not capabilities.evidence_stores:
        blockers.append(
            PlanningBlocker(
                "EVIDENCE_STORE_REQUIRED",
                "Production plans require at least one adapter-declared evidence store.",
            )
        )


def _match_hash_diff(capabilities: PlatformCapabilities, blockers: list[PlanningBlocker]) -> None:
    if not capabilities.supports_merge:
        blockers.append(PlanningBlocker("MERGE_UNSUPPORTED", "SCD1 hash diff requires merge capability."))
    if not capabilities.supports_hash_diff:
        blockers.append(
            PlanningBlocker("HASH_DIFF_UNSUPPORTED", "SCD1 hash diff requires hash-diff change detection capability.")
        )


def _match_scd2(capabilities: PlatformCapabilities, blockers: list[PlanningBlocker]) -> None:
    if not capabilities.supports_merge:
        blockers.append(PlanningBlocker("MERGE_UNSUPPORTED", "SCD2 requires merge capability."))
    if not capabilities.supports_scd2:
        blockers.append(PlanningBlocker("SCD2_UNSUPPORTED", "Historical SCD2 semantics are not supported."))


def _validate_write_semantics(contract: SemanticContract, blockers: list[PlanningBlocker]) -> None:
    mode = contract.write.mode
    if mode in {"scd1_upsert", "snapshot_soft_delete", "scd2_historical"} and not contract.write.merge_keys:
        blockers.append(PlanningBlocker("MERGE_KEYS_REQUIRED", f"{mode} requires merge_keys."))
    if (
        mode == "scd1_hash_diff"
        and contract.write.hash_strategy != "all_columns_except"
        and not contract.write.hash_keys
    ):
        blockers.append(
            PlanningBlocker(
                "HASH_KEYS_REQUIRED",
                "scd1_hash_diff requires hash_keys unless hash_strategy=all_columns_except.",
            )
        )
    scd2_only = {
        "scd2_effective_from_column": contract.write.scd2_effective_from_column,
        "scd2_sequence_by": contract.write.scd2_sequence_by,
        "scd2_late_arriving_policy": (
            contract.write.scd2_late_arriving_policy if contract.write.scd2_late_arriving_policy != "apply" else None
        ),
        "scd2_apply_as_deletes": contract.write.scd2_apply_as_deletes,
    }
    if mode != "scd2_historical":
        configured = [name for name, value in scd2_only.items() if value]
        if configured:
            blockers.append(
                PlanningBlocker(
                    "SCD2_FIELDS_ON_NON_SCD2_MODE",
                    f"{', '.join(configured)} are only supported with scd2_historical.",
                )
            )
    if (
        mode == "scd2_historical"
        and contract.write.scd2_late_arriving_policy in {"ignore", "reject"}
        and not contract.write.scd2_sequence_by
    ):
        blockers.append(
            PlanningBlocker(
                "SCD2_SEQUENCE_BY_REQUIRED",
                "scd2_late_arriving_policy=ignore/reject requires scd2_sequence_by.",
            )
        )
    if mode == "snapshot_soft_delete" and not _source_declares_complete_snapshot(contract):
        blockers.append(
            PlanningBlocker(
                "SNAPSHOT_SOURCE_COMPLETE_REQUIRED",
                "snapshot_soft_delete requires source.read.source_complete=true or source.read.full_snapshot=true.",
            )
        )


def _source_declares_complete_snapshot(contract: SemanticContract) -> bool:
    source = contract.source.raw or {}
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    return bool(read.get("source_complete") or read.get("full_snapshot") or source.get("source_complete"))
