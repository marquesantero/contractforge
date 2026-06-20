"""Architecture review for governed execution projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArchitectureConceptFinding:
    """One detected governed-execution architecture concept."""

    concept: str
    status: str
    evidence: list[str] = field(default_factory=list)
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept": self.concept,
            "status": self.status,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class ArchitectureReview:
    """Structured review for a governed execution repository."""

    root: str
    findings: list[ArchitectureConceptFinding]

    @property
    def detected_count(self) -> int:
        return sum(1 for finding in self.findings if finding.status == "detected")

    @property
    def score(self) -> float:
        return self.detected_count / len(self.findings) if self.findings else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "score": self.score,
            "detected_count": self.detected_count,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Governed Architecture Review",
            "",
            f"- Root: `{self.root}`",
            f"- Score: `{self.score:.0%}`",
            f"- Concepts detected: `{self.detected_count}/{len(self.findings)}`",
            "",
            "## Findings",
            "",
        ]
        for finding in self.findings:
            lines.append(f"### {finding.concept}")
            lines.append("")
            lines.append(f"- Status: `{finding.status}`")
            if finding.evidence:
                lines.extend(["- Evidence:", *[f"  - `{item}`" for item in finding.evidence]])
            if finding.recommendation:
                lines.append(f"- Recommendation: {finding.recommendation}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def review_governed_architecture(root: str | Path) -> ArchitectureReview:
    """Review a repository for reusable governed-execution concepts."""

    root_path = Path(root)
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"Architecture review root must be an existing directory: {root_path}")
    files = [path for path in root_path.rglob("*") if path.is_file() and _is_text_candidate(path)]
    index = _RepositoryIndex(root_path, files)
    return ArchitectureReview(
        root=str(root_path),
        findings=[
            _concept(index, "Typed intent/signature model", ("StateSignature", "IntentSpec", "SignatureConstraints", "SemanticResolution")),
            _concept(index, "Policy gate before execution/generation", ("PolicyEngine", "PolicyRule", "GenerationPolicyEngine", "policy_evaluation")),
            _concept(index, "Context registry or project-state snapshot", ("ContextRegistry", "ContextSnapshot", "ProjectState", "snapshot_hash")),
            _concept(index, "Tamper-evident audit trail", ("AuditTrail", "GenerationAuditTrail", "event_hash", "previous_hash")),
            _concept(index, "Planner before code/artifact generation", ("ExecutionPlanner", "GapPlan", "TransformationPlan", "plan_project_gaps")),
            _concept(index, "Validation before readiness", ("StaticValidator", "RuntimeValidator", "validate_project_plan_artifact", "DeterministicValidationReport")),
            _concept(index, "Lifecycle or operational scoring", ("IndexCalculator", "PromotionEngine", "IFo", "IDI", "control-table")),
        ],
    )


def _concept(index: _RepositoryIndex, name: str, tokens: tuple[str, ...]) -> ArchitectureConceptFinding:
    evidence = index.find_any(tokens)
    if evidence:
        return ArchitectureConceptFinding(concept=name, status="detected", evidence=evidence[:5])
    return ArchitectureConceptFinding(
        concept=name,
        status="missing",
        recommendation=f"Consider adding an explicit {name.lower()} if this repository needs governed AI/data execution.",
    )


def _is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in {".py", ".md", ".yml", ".yaml", ".json", ".toml", ".txt"}


class _RepositoryIndex:
    def __init__(self, root: Path, files: list[Path]) -> None:
        self.root = root
        self.files = files

    def find_any(self, tokens: tuple[str, ...]) -> list[str]:
        evidence: list[str] = []
        lowered_tokens = tuple(token.lower() for token in tokens)
        for path in self.files:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            if any(token in content for token in lowered_tokens):
                evidence.append(path.relative_to(self.root).as_posix())
        return evidence
