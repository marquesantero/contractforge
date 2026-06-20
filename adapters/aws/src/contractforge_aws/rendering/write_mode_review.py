"""Render AWS write-mode review notes."""

from __future__ import annotations

from collections.abc import Callable

from contractforge_core.semantic import SemanticContract


def render_write_mode_review(contract: SemanticContract) -> str:
    renderer = _RENDERERS.get(contract.write.mode, _default_review)
    return renderer(contract)


def should_render_write_mode_review(contract: SemanticContract) -> bool:
    return contract.write.mode in _RENDERERS


def _scd2_review(contract: SemanticContract) -> str:
    return _review(
        contract,
        title="AWS SCD2 Historical Review",
        mapping="Apache Iceberg MERGE plus effective-dated history columns in Glue Spark.",
        checks=[
            "Confirm merge keys uniquely identify the business entity.",
            "Confirm sequence/effective-date ordering and late-arriving policy.",
            "Confirm delete semantics, including whether tombstones expire current records.",
            "Validate concurrent writer behavior and compaction policy before production.",
        ],
    )


def _snapshot_review(contract: SemanticContract) -> str:
    return _review(
        contract,
        title="AWS Snapshot Soft Delete Review",
        mapping="Full snapshot reconciliation plus Iceberg MERGE in Glue Spark.",
        checks=[
            "Prove the source snapshot is complete for the target grain.",
            "Confirm missing source rows should be expired or marked deleted.",
            "Validate large anti-join cost and Iceberg file rewrite impact.",
            "Define recovery behavior for partial or stale snapshots.",
        ],
    )


def _default_review(contract: SemanticContract) -> str:
    return _review(
        contract,
        title="AWS Write Mode Review",
        mapping="AWS Glue Spark writing Apache Iceberg.",
        checks=["No additional review notes are declared for this write mode."],
    )


def _review(contract: SemanticContract, *, title: str, mapping: str, checks: list[str]) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Target: `{contract.target.namespace or 'default'}.{contract.target.name}`",
        f"- Write mode: `{contract.write.mode}`",
        f"- AWS mapping: {mapping}",
        "- Status: `REVIEW_REQUIRED`",
        "",
        "## Required Review",
        "",
    ]
    lines.extend(f"- {item}" for item in checks)
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "The AWS adapter must not render an executable job for this mode until these semantics are validated with real Glue/Iceberg integration tests.",
            "",
        ]
    )
    return "\n".join(lines)


_RENDERERS: dict[str, Callable[[SemanticContract], str]] = {
    "scd2_historical": _scd2_review,
    "snapshot_soft_delete": _snapshot_review,
}
