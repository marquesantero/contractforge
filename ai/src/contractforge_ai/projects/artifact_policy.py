"""Artifact policy for generated project outputs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from contractforge_ai.projects.models import ProjectArtifact

HUMAN_REVIEW_MARKDOWN_PATHS = {
    "AI_REVIEW.md",
    "CONTEXT.md",
    "DECISIONS.md",
    "MIGRATION.md",
    "RUNBOOK.md",
    "VALIDATION.md",
}


def is_human_review_markdown(path: str, *, extra_paths: Iterable[str] | None = None) -> bool:
    """Return whether an artifact is a human-review Markdown file superseded by HTML."""

    normalized = path.replace("\\", "/")
    extra = {item.replace("\\", "/") for item in extra_paths or []}
    return normalized in HUMAN_REVIEW_MARKDOWN_PATHS or normalized in extra


def compact_human_review_artifacts(
    artifacts: Iterable[ProjectArtifact],
    *,
    extra_paths: Iterable[str] | None = None,
) -> list[ProjectArtifact]:
    """Remove verbose human-review Markdown artifacts from generated project outputs."""

    return [artifact for artifact in artifacts if not is_human_review_markdown(artifact.path, extra_paths=extra_paths)]


@dataclass(frozen=True)
class CompactedArtifacts:
    """Generated artifacts split into files to write and Markdown content to consolidate."""

    kept: list[ProjectArtifact]
    consolidated: list[ProjectArtifact]


def split_human_review_artifacts(
    artifacts: Iterable[ProjectArtifact],
    *,
    extra_paths: Iterable[str] | None = None,
) -> CompactedArtifacts:
    """Split implementation artifacts from human-review Markdown superseded by rich HTML."""

    kept: list[ProjectArtifact] = []
    consolidated: list[ProjectArtifact] = []
    for artifact in artifacts:
        if is_human_review_markdown(artifact.path, extra_paths=extra_paths):
            consolidated.append(artifact)
        else:
            kept.append(artifact)
    return CompactedArtifacts(kept=kept, consolidated=consolidated)
