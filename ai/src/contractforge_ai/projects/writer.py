"""Filesystem writer for generated project plans."""

from __future__ import annotations

from pathlib import Path

from contractforge_ai.projects.artifact_policy import compact_human_review_artifacts
from contractforge_ai.projects.models import ArtifactWriteResult, ProjectArtifact, ProjectPlan
from contractforge_ai.reports import render_project_plan_review


def write_project_plan(
    plan: ProjectPlan,
    output_dir: str | Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> list[ArtifactWriteResult]:
    """Write project artifacts under an output directory.

    Existing files are skipped by default. Set `force=True` to overwrite them explicitly.
    Set `dry_run=True` to return the planned write operations without touching the filesystem.
    """

    root = Path(output_dir).resolve()
    results: list[ArtifactWriteResult] = []

    artifacts = compact_human_review_artifacts(plan.artifacts)
    if not any(artifact.path.endswith(".html") for artifact in artifacts):
        compact_plan = ProjectPlan(
            name=plan.name,
            target=plan.target,
            artifacts=artifacts,
            report=plan.report,
            traceability=plan.traceability,
        )
        review = render_project_plan_review(compact_plan, title=f"{plan.name} Project Review")
        artifacts = [
            *artifacts,
            ProjectArtifact(
                path="PROJECT_REVIEW.html",
                kind="other",
                description="Consolidated human-facing project review.",
                content=review.html,
            ),
        ]

    for artifact in artifacts:
        target = _resolve_artifact_path(root, artifact)
        relative = _relative_to_root(root, target)

        if target.exists() and not force:
            results.append(
                ArtifactWriteResult(
                    path=relative,
                    status="skipped",
                    reason="File already exists. Use force=True to overwrite.",
                )
            )
            continue

        status = "overwritten" if target.exists() else "created"
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(artifact.content, encoding="utf-8", newline="\n")

        results.append(ArtifactWriteResult(path=relative, status=status))

    return results


def _resolve_artifact_path(root: Path, artifact: ProjectArtifact) -> Path:
    target = (root / artifact.path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Artifact path escapes output directory: {artifact.path!r}.") from exc
    return target


def _relative_to_root(root: Path, target: Path) -> str:
    return target.relative_to(root).as_posix()
