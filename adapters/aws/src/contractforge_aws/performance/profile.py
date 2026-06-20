"""Render AWS runtime performance benchmark profiles."""

from __future__ import annotations

import json

from contractforge_core.semantic import SemanticContract
from contractforge_aws.rendering.names import iceberg_table_name

_PROFILED_WRITE_MODES = frozenset({"scd1_hash_diff"})


def should_render_performance_profile(contract: SemanticContract) -> bool:
    return contract.write.mode in _PROFILED_WRITE_MODES


def render_performance_profile(contract: SemanticContract) -> str:
    """Render a deterministic benchmark checklist for runtime-risky contracts."""

    payload = {
        "kind": "contractforge.aws.performance_profile.v1",
        "subtarget": "aws_glue_iceberg",
        "status": "benchmark_required",
        "warning_code": _warning_code(contract),
        "target_table": iceberg_table_name(contract),
        "write_mode": contract.write.mode,
        "merge_keys": list(contract.write.merge_keys),
        "hash_strategy": contract.write.hash_strategy,
        "hash_keys": list(contract.write.hash_keys),
        "hash_exclude_columns": list(contract.write.hash_exclude_columns),
        "required_metrics": list(_REQUIRED_METRICS),
        "benchmark_cases": list(_benchmark_cases(contract)),
        "release_gate": _release_gate(contract),
        "artifact_size_source": "deployment_manifest.artifact_summary.runtime_artifact_bytes",
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _warning_code(contract: SemanticContract) -> str:
    if contract.write.mode == "scd1_hash_diff":
        return "AWS_HASH_DIFF_PERFORMANCE_UNVALIDATED"
    return "AWS_PERFORMANCE_UNVALIDATED"


def _benchmark_cases(contract: SemanticContract) -> tuple[dict[str, object], ...]:
    if contract.write.mode == "scd1_hash_diff":
        return (
            {
                "name": "initial_load",
                "purpose": "Measure bootstrap table creation and first Iceberg snapshot cost.",
                "expected_observations": ["rows_read", "rows_written", "duration_seconds", "dpu_seconds"],
            },
            {
                "name": "no_change_replay",
                "purpose": "Confirm hash diff skips no-op updates and keeps rewritten files low.",
                "expected_observations": ["rows_read", "rows_updated", "duration_seconds", "iceberg_snapshot_delta"],
            },
            {
                "name": "changed_row_wave",
                "purpose": "Measure merge cost when a representative subset changes.",
                "expected_observations": ["rows_updated", "files_rewritten", "duration_seconds", "dpu_seconds"],
            },
            {
                "name": "concurrent_or_overlap_guard",
                "purpose": "Document whether overlapping Glue runs are prevented or safely serialized.",
                "expected_observations": ["job_run_overlap_policy", "iceberg_commit_conflict_behavior"],
            },
            {
                "name": "duplicate_key_failure",
                "purpose": "Confirm duplicate merge keys fail before write with redacted failed-run evidence.",
                "expected_observations": ["failed_run_status", "redacted_error_evidence", "no_target_mutation"],
            },
            {
                "name": "null_key_failure",
                "purpose": "Confirm null merge keys fail before write with redacted failed-run evidence.",
                "expected_observations": ["failed_run_status", "redacted_error_evidence", "no_target_mutation"],
            },
        )
    return ()


def _release_gate(contract: SemanticContract) -> dict[str, object]:
    return {
        "stable_claim_allowed": False,
        "reason": (
            "Runtime script is generated, but production certification requires a benchmark profile "
            "captured from real Glue/Iceberg runs."
        ),
        "planner_status_until_validated": "SUPPORTED_WITH_WARNINGS",
        "mode": contract.write.mode,
    }


_REQUIRED_METRICS = (
    "glue_version",
    "worker_type",
    "worker_count",
    "dpu_seconds",
    "source_row_count",
    "target_written_row_count",
    "quarantined_row_count",
    "merge_key_cardinality",
    "iceberg_snapshot_before",
    "iceberg_snapshot_after",
    "job_duration_seconds",
    "generated_job_script_bytes",
)
