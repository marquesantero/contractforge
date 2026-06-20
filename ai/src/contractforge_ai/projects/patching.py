"""Patch planning for existing generated project directories."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from contractforge_ai.projects.models import ProjectArtifact, ProjectPlan

PatchAction = Literal["create", "update", "preserve", "conflict"]


@dataclass(frozen=True)
class ArtifactPatch:
    """Reviewable patch decision for one generated artifact."""

    path: str
    action: PatchAction
    reason: str
    artifact_kind: str
    current_hash: str | None = None
    proposed_hash: str | None = None

    @property
    def writes_file(self) -> bool:
        return self.action in {"create", "update"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "action": self.action,
            "reason": self.reason,
            "artifact_kind": self.artifact_kind,
            "current_hash": self.current_hash,
            "proposed_hash": self.proposed_hash,
            "writes_file": self.writes_file,
        }


@dataclass(frozen=True)
class ProjectPatchPlan:
    """Patch plan for applying a generated project to an existing directory."""

    root: str
    patches: list[ArtifactPatch] = field(default_factory=list)

    @property
    def creates(self) -> int:
        return self._count("create")

    @property
    def updates(self) -> int:
        return self._count("update")

    @property
    def preserves(self) -> int:
        return self._count("preserve")

    @property
    def conflicts(self) -> int:
        return self._count("conflict")

    @property
    def has_conflicts(self) -> bool:
        return self.conflicts > 0

    def _count(self, action: PatchAction) -> int:
        return sum(1 for patch in self.patches if patch.action == action)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "creates": self.creates,
            "updates": self.updates,
            "preserves": self.preserves,
            "conflicts": self.conflicts,
            "patches": [patch.to_dict() for patch in self.patches],
        }


def plan_project_patches(
    project: ProjectPlan,
    root: str | Path,
    *,
    allow_updates: bool = False,
    conflict_on_review_artifacts: bool = False,
) -> ProjectPatchPlan:
    """Plan how generated artifacts would affect an existing project directory."""

    root_path = Path(root).resolve()
    patches = [
        _plan_artifact_patch(
            artifact,
            root=root_path,
            allow_updates=allow_updates,
            conflict_on_review_artifacts=conflict_on_review_artifacts,
        )
        for artifact in project.artifacts
    ]
    return ProjectPatchPlan(root=str(root_path), patches=patches)


def _plan_artifact_patch(
    artifact: ProjectArtifact,
    *,
    root: Path,
    allow_updates: bool,
    conflict_on_review_artifacts: bool,
) -> ArtifactPatch:
    target = _resolve_artifact_path(root, artifact)
    proposed_hash = _content_hash(artifact.content)
    if not target.exists():
        return ArtifactPatch(
            path=artifact.path,
            action="create",
            reason="Artifact does not exist in the target project.",
            artifact_kind=artifact.kind,
            proposed_hash=proposed_hash,
        )

    current_content = target.read_text(encoding="utf-8")
    current_hash = _content_hash(current_content)
    if current_hash == proposed_hash:
        return ArtifactPatch(
            path=artifact.path,
            action="preserve",
            reason="Existing artifact content matches the generated artifact.",
            artifact_kind=artifact.kind,
            current_hash=current_hash,
            proposed_hash=proposed_hash,
        )

    if conflict_on_review_artifacts and artifact.path.upper().endswith(("AI_REVIEW.HTML", "PROJECT_REVIEW.HTML")):
        return ArtifactPatch(
            path=artifact.path,
            action="conflict",
            reason="Review artifacts differ and were configured to require explicit conflict resolution.",
            artifact_kind=artifact.kind,
            current_hash=current_hash,
            proposed_hash=proposed_hash,
        )

    if allow_updates:
        return ArtifactPatch(
            path=artifact.path,
            action="update",
            reason="Existing artifact differs and updates are explicitly allowed.",
            artifact_kind=artifact.kind,
            current_hash=current_hash,
            proposed_hash=proposed_hash,
        )

    return ArtifactPatch(
        path=artifact.path,
        action="conflict",
        reason="Existing artifact differs. Enable updates explicitly or review the patch manually.",
        artifact_kind=artifact.kind,
        current_hash=current_hash,
        proposed_hash=proposed_hash,
    )


def _resolve_artifact_path(root: Path, artifact: ProjectArtifact) -> Path:
    target = (root / artifact.path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Artifact path escapes output directory: {artifact.path!r}.") from exc
    return target


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
