"""Models for ContractForge project-structure validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from contractforge_ai.models import EvidenceItem, Finding

ProjectFileKind = Literal["project", "environment", "connection", "ingestion_bundle"]
ProjectStructureStatus = Literal["READY", "READY_WITH_WARNINGS", "NEEDS_DECISIONS", "INVALID", "UNSAFE"]


@dataclass(frozen=True)
class ProjectStructureFile:
    """A discovered project file with its logical role."""

    kind: ProjectFileKind
    path: Path
    adapter: str | None = None
    name: str | None = None

    def to_dict(self, *, root: Path) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": _relative(self.path, root),
            **({"adapter": self.adapter} if self.adapter else {}),
            **({"name": self.name} if self.name else {}),
        }


@dataclass(frozen=True)
class ProjectStructureReport:
    """Result for deterministic validation of an on-disk ContractForge project."""

    root: Path
    status: ProjectStructureStatus
    summary: str
    files: list[ProjectStructureFile] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status in {"READY", "READY_WITH_WARNINGS"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "status": self.status,
            "ready": self.ready,
            "summary": self.summary,
            "files": [item.to_dict(root=self.root) for item in self.files],
            "findings": [finding.to_dict() for finding in self.findings],
            "evidence": [item.to_dict() for item in self.evidence],
        }


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
