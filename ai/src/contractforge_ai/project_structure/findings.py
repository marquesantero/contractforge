"""Finding builders for project-structure validation."""

from __future__ import annotations

from pathlib import Path

from contractforge_ai.models import EvidenceItem, Finding, Severity


def finding(
    *,
    code: str,
    severity: Severity,
    title: str,
    detail: str,
    recommendation: str,
    path: str | Path | None = None,
    source: str = "project_structure",
) -> Finding:
    rendered_path = str(path) if path is not None else None
    return Finding(
        code=code,
        severity=severity,
        title=title,
        detail=detail,
        recommendation=recommendation,
        path=rendered_path,
        evidence=[
            EvidenceItem(
                source=source,
                path=rendered_path,
                reason=f"Deterministic project-structure rule {code!r} identified this condition.",
                confidence=1.0,
            )
        ],
    )


def evidence(source: str, reason: str, *, path: str | Path | None = None) -> EvidenceItem:
    return EvidenceItem(source=source, path=str(path) if path is not None else None, reason=reason, confidence=1.0)
