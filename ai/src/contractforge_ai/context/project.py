"""Context packaging for project synthesis."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from contractforge_ai.models import EvidenceItem, RequiredDecision, Traceability

RuntimeTarget = Literal["databricks-serverless", "databricks-classic", "local", "unknown"]

SAMPLE_SUFFIXES = {".json", ".jsonl", ".ndjson", ".csv", ".yaml", ".yml"}
MAX_SAMPLE_FILES = 20
MAX_TEXT_PREVIEW = 4096


@dataclass(frozen=True)
class ContextFile:
    """One file discovered as synthesis context."""

    path: str
    kind: str
    format: str
    size_bytes: int
    records_sampled: int = 0
    preview: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "path": self.path,
            "kind": self.kind,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "records_sampled": self.records_sampled,
            "preview": self.preview,
        }
        return {key: value for key, value in payload.items() if value not in (None, [], {})}


@dataclass(frozen=True)
class ProjectContextPackage:
    """Structured context used before generating a ContractForge project."""

    intent: str
    context_dir: str | None = None
    schema_path: str | None = None
    runtime: RuntimeTarget = "unknown"
    files: list[ContextFile] = field(default_factory=list)
    inferred_schema: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    decisions_required: list[RequiredDecision] = field(default_factory=list)
    traceability: Traceability = field(default_factory=Traceability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "context_dir": self.context_dir,
            "schema_path": self.schema_path,
            "runtime": self.runtime,
            "files": [item.to_dict() for item in self.files],
            "inferred_schema": self.inferred_schema,
            "warnings": self.warnings,
            "decisions_required": [item.to_dict() for item in self.decisions_required],
            "traceability": self.traceability.to_dict(),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Project Context",
            "",
            f"- Runtime: `{self.runtime}`",
            f"- Context directory: `{self.context_dir or 'not provided'}`",
            f"- Explicit schema: `{self.schema_path or 'not provided'}`",
            f"- Files considered: `{len(self.files)}`",
        ]
        if self.inferred_schema:
            columns = self.inferred_schema.get("columns", [])
            lines.extend(["", "## Inferred Schema", f"- Columns: `{len(columns)}`"])
            for column in columns:
                lines.append(f"- `{column['name']}`: `{column['type']}`")
        if self.warnings:
            lines.extend(["", "## Warnings", *[f"- {warning}" for warning in self.warnings]])
        if self.decisions_required:
            lines.extend(["", "## Decisions Required", *[item.to_markdown() for item in self.decisions_required]])
        lines.extend(["", self.traceability.to_markdown()])
        return "\n".join(lines).rstrip() + "\n"


def build_project_context_package(
    *,
    intent: str,
    context_dir: str | Path | None = None,
    schema_path: str | Path | None = None,
    runtime: str | None = None,
) -> ProjectContextPackage:
    """Build deterministic context for project synthesis."""

    files: list[ContextFile] = []
    warnings: list[str] = []
    decisions: list[RequiredDecision] = []
    inferred_schema: dict[str, Any] | None = None

    if context_dir:
        root = Path(context_dir)
        if not root.exists() or not root.is_dir():
            raise ValueError(f"context_dir must be an existing directory: {root}")
        files = _discover_context_files(root, warnings)
        inferred_schema = _infer_schema_from_files(files)
    elif not schema_path:
        decisions.append(
            RequiredDecision(
                question="Provide schema_path or context_dir.",
                reason="Project synthesis needs either an explicit schema/profile file or sample files for schema inference.",
                path="schema_path",
            )
        )

    if not schema_path and inferred_schema is None:
        decisions.append(
            RequiredDecision(
                question="Provide a schema/profile file or supported JSON/CSV sample.",
                reason="No usable schema evidence was found in the context package.",
                path="context_dir",
            )
        )

    normalized_runtime = _runtime(runtime)
    if normalized_runtime == "unknown":
        warnings.append("Runtime was not provided. Runtime-specific dependency and compute recommendations remain generic.")

    evidence = [
        EvidenceItem(
            source="project_context",
            path=str(context_dir) if context_dir else None,
            reason="Built deterministic context package for project synthesis.",
            value={
                "files": len(files),
                "has_explicit_schema": bool(schema_path),
                "has_inferred_schema": inferred_schema is not None,
                "runtime": normalized_runtime,
            },
            confidence=0.82 if schema_path or inferred_schema else 0.45,
        )
    ]

    return ProjectContextPackage(
        intent=intent,
        context_dir=str(context_dir) if context_dir else None,
        schema_path=str(schema_path) if schema_path else None,
        runtime=normalized_runtime,
        files=files,
        inferred_schema=inferred_schema,
        warnings=warnings,
        decisions_required=decisions,
        traceability=Traceability(
            confidence=0.82 if schema_path or inferred_schema else 0.45,
            evidence=evidence,
            decisions_required=decisions,
            review_required=bool(decisions or warnings),
        ),
    )


def schema_profile_to_yaml(schema_profile: dict[str, Any]) -> str:
    """Serialize an inferred schema profile for generated project artifacts."""

    return yaml.safe_dump(schema_profile, sort_keys=False)


def _discover_context_files(root: Path, warnings: list[str]) -> list[ContextFile]:
    candidates = [path for path in sorted(root.rglob("*")) if path.is_file() and path.suffix.lower() in SAMPLE_SUFFIXES]
    if len(candidates) > MAX_SAMPLE_FILES:
        warnings.append(f"Context directory contains {len(candidates)} supported sample files; only the first {MAX_SAMPLE_FILES} were inspected.")
    return [_inspect_context_file(path, root) for path in candidates[:MAX_SAMPLE_FILES]]


def _inspect_context_file(path: Path, root: Path) -> ContextFile:
    suffix = path.suffix.lower()
    relative = path.relative_to(root).as_posix()
    size_bytes = path.stat().st_size
    if suffix == ".json":
        return _inspect_json(path, relative, size_bytes)
    if suffix in {".jsonl", ".ndjson"}:
        return _inspect_json_lines(path, relative, size_bytes)
    if suffix == ".csv":
        return _inspect_csv(path, relative, size_bytes)
    return _inspect_text(path, relative, size_bytes, suffix.lstrip("."))


def _inspect_json(path: Path, relative: str, size_bytes: int) -> ContextFile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sample = payload[0] if isinstance(payload, list) and payload else payload
    records = len(payload) if isinstance(payload, list) else 1
    return ContextFile(
        path=relative,
        kind="sample",
        format="json",
        size_bytes=size_bytes,
        records_sampled=records,
        preview=sample if isinstance(sample, dict) else {"value": sample},
    )


def _inspect_json_lines(path: Path, relative: str, size_bytes: int) -> ContextFile:
    preview: dict[str, Any] | None = None
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            count += 1
            if preview is None:
                payload = json.loads(line)
                preview = payload if isinstance(payload, dict) else {"value": payload}
            if count >= 50:
                break
    return ContextFile(
        path=relative,
        kind="sample",
        format="jsonl",
        size_bytes=size_bytes,
        records_sampled=count,
        preview=preview or {},
    )


def _inspect_csv(path: Path, relative: str, size_bytes: int) -> ContextFile:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        row = next(reader, None) or {}
    return ContextFile(
        path=relative,
        kind="sample",
        format="csv",
        size_bytes=size_bytes,
        records_sampled=1 if row else 0,
        preview=row,
    )


def _inspect_text(path: Path, relative: str, size_bytes: int, fmt: str) -> ContextFile:
    return ContextFile(
        path=relative,
        kind="metadata",
        format=fmt,
        size_bytes=size_bytes,
        preview=path.read_text(encoding="utf-8")[:MAX_TEXT_PREVIEW],
    )


def _infer_schema_from_files(files: list[ContextFile]) -> dict[str, Any] | None:
    for item in files:
        if item.format in {"json", "jsonl", "csv"} and isinstance(item.preview, dict) and item.preview:
            return {
                "columns": [
                    {
                        "name": str(name),
                        "type": _infer_type(value),
                        "nullable": value is None,
                    }
                    for name, value in item.preview.items()
                ]
            }
    return None


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "long"
    if isinstance(value, float):
        return "double"
    if isinstance(value, dict):
        return "struct"
    if isinstance(value, list):
        return "array"
    return "string"


def _runtime(value: str | None) -> RuntimeTarget:
    normalized = (value or "unknown").strip().lower().replace("_", "-")
    if normalized in {"serverless", "databricks-serverless"}:
        return "databricks-serverless"
    if normalized in {"classic", "single-node", "job-cluster", "databricks-classic"}:
        return "databricks-classic"
    if normalized in {"local", "local-cli"}:
        return "local"
    return "unknown"
