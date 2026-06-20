"""Models for generated multi-file projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_ai.models import Assumption, RequiredDecision, Traceability

ArtifactKind = Literal[
    "contract",
    "annotation",
    "operation",
    "access",
    "notebook",
    "python",
    "sql",
    "yaml",
    "json",
    "markdown",
    "config",
    "resource",
    "other",
]
WriteStatus = Literal["created", "skipped", "overwritten"]


@dataclass(frozen=True)
class ProjectArtifact:
    """A file artifact that may be written as part of a generated project."""

    path: str
    content: str
    kind: ArtifactKind = "other"
    description: str | None = None
    executable: bool = False

    def __post_init__(self) -> None:
        if not self.path or self.path.strip() != self.path:
            raise ValueError("Artifact path must be non-empty and cannot have leading/trailing whitespace.")
        normalized = self.path.replace("\\", "/")
        if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized or normalized == "..":
            raise ValueError(f"Artifact path must be relative and stay inside the output directory: {self.path!r}.")
        if "\x00" in normalized:
            raise ValueError("Artifact path cannot contain null bytes.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "description": self.description,
            "executable": self.executable,
            "content_length": len(self.content),
        }


@dataclass(frozen=True)
class DecisionReport:
    """Human review context for a generated project."""

    title: str
    summary: str
    assumptions: list[Assumption] = field(default_factory=list)
    decisions_required: list[RequiredDecision] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "assumptions": [item.to_dict() for item in self.assumptions],
            "decisions_required": [item.to_dict() for item in self.decisions_required],
            "warnings": self.warnings,
        }

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", self.summary]
        if self.warnings:
            lines.extend(["", "## Warnings", *[f"- {warning}" for warning in self.warnings]])
        if self.assumptions:
            lines.extend(["", "## Assumptions", *[item.to_markdown() for item in self.assumptions]])
        if self.decisions_required:
            lines.extend(["", "## Decisions Required", *[item.to_markdown() for item in self.decisions_required]])
        return "\n".join(lines).rstrip() + "\n"


@dataclass(frozen=True)
class ProjectPlan:
    """A normalized generated project plan."""

    name: str
    target: str
    artifacts: list[ProjectArtifact]
    report: DecisionReport
    traceability: Traceability = field(default_factory=Traceability)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ProjectPlan name cannot be empty.")
        if not self.target.strip():
            raise ValueError("ProjectPlan target cannot be empty.")
        paths = [artifact.path.replace("\\", "/") for artifact in self.artifacts]
        duplicated = sorted({path for path in paths if paths.count(path) > 1})
        if duplicated:
            raise ValueError(f"Duplicate artifact path(s): {', '.join(duplicated)}.")

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        artifacts = []
        for artifact in self.artifacts:
            payload = artifact.to_dict()
            if include_content:
                payload["content"] = artifact.content
            artifacts.append(payload)
        return {
            "name": self.name,
            "target": self.target,
            "artifacts": artifacts,
            "report": self.report.to_dict(),
            "traceability": self.traceability.to_dict(),
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Project Plan: {self.name}",
            "",
            f"- Target: `{self.target}`",
            f"- Artifacts: `{len(self.artifacts)}`",
            "",
            "## Artifacts",
        ]
        for artifact in self.artifacts:
            description = f" - {artifact.description}" if artifact.description else ""
            lines.append(f"- `{artifact.path}` ({artifact.kind}){description}")
        lines.extend(["", self.report.to_markdown().rstrip(), "", self.traceability.to_markdown()])
        return "\n".join(lines).rstrip() + "\n"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProjectPlan:
        """Build a project plan from a JSON/YAML-compatible mapping."""

        report_payload = _mapping(payload.get("report"))
        traceability_payload = _mapping(payload.get("traceability"))
        return cls(
            name=str(payload.get("name") or ""),
            target=str(payload.get("target") or ""),
            artifacts=[
                ProjectArtifact(
                    path=str(item.get("path") or ""),
                    content=str(item.get("content") or ""),
                    kind=item.get("kind") or "other",
                    description=item.get("description"),
                    executable=bool(item.get("executable", False)),
                )
                for item in payload.get("artifacts", [])
                if isinstance(item, dict)
            ],
            report=DecisionReport(
                title=str(report_payload.get("title") or payload.get("name") or "Generated Project"),
                summary=str(report_payload.get("summary") or "Generated project plan."),
                assumptions=[
                    Assumption(
                        statement=str(item.get("statement") or ""),
                        confidence=float(item.get("confidence", 0.5)),
                        review_required=bool(item.get("review_required", True)),
                    )
                    for item in report_payload.get("assumptions", [])
                    if isinstance(item, dict)
                ],
                decisions_required=[
                    RequiredDecision(
                        question=str(item.get("question") or ""),
                        reason=str(item.get("reason") or ""),
                        path=item.get("path"),
                        options=[str(option) for option in item.get("options", [])],
                    )
                    for item in report_payload.get("decisions_required", [])
                    if isinstance(item, dict)
                ],
                warnings=[str(item) for item in report_payload.get("warnings", [])],
            ),
            traceability=Traceability(
                confidence=float(traceability_payload.get("confidence", 1.0)),
                review_required=bool(traceability_payload.get("review_required", False)),
            ),
        )


@dataclass(frozen=True)
class ArtifactWriteResult:
    """Result of writing one project artifact."""

    path: str
    status: WriteStatus
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"path": self.path, "status": self.status, "reason": self.reason}
        return {key: value for key, value in payload.items() if value is not None}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
