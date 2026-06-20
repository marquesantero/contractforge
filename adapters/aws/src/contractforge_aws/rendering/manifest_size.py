"""Deployment manifest size-budget helpers."""

from __future__ import annotations


RUNTIME_WARNING_BYTES = 262_144


def artifact_summary(artifacts: dict[str, str]) -> dict[str, int]:
    sizes = [len(body.encode("utf-8")) for body in artifacts.values()]
    return {
        "artifact_count": len(artifacts),
        "total_bytes": sum(sizes),
        "max_artifact_bytes": max(sizes, default=0),
        "runtime_artifact_bytes": sum(
            len(body.encode("utf-8")) for name, body in artifacts.items() if name.endswith(".glue_job.py")
        ),
    }


def artifact_size_budget(artifacts: dict[str, str]) -> dict[str, object]:
    summary = artifact_summary(artifacts)
    runtime_bytes = summary["runtime_artifact_bytes"]
    return {
        "runtime_warning_bytes": RUNTIME_WARNING_BYTES,
        "runtime_artifact_bytes": runtime_bytes,
        "runtime_status": "WARN" if runtime_bytes > RUNTIME_WARNING_BYTES else "OK",
    }
