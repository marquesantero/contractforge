"""Project-state discovery for agentic generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from contractforge_ai.agentic.models import ContractSummary, Layer, ProjectState


def analyze_project_state(root: str | Path | None) -> ProjectState:
    """Inspect an existing ContractForge project directory."""

    if root is None:
        return ProjectState(root=None)
    root_path = Path(root)
    if not root_path.exists():
        return ProjectState(root=str(root_path), warnings=[f"Project root does not exist: {root_path}"])
    if not root_path.is_dir():
        return ProjectState(root=str(root_path), warnings=[f"Project root is not a directory: {root_path}"])

    contracts: list[ContractSummary] = []
    warnings: list[str] = []
    for path in sorted(root_path.rglob("*.ingestion.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append(f"Could not parse {path.relative_to(root_path).as_posix()}: {type(exc).__name__}: {exc}")
            continue
        if not isinstance(payload, dict):
            warnings.append(f"Ignored non-mapping contract: {path.relative_to(root_path).as_posix()}")
            continue
        contracts.append(_contract_summary(root_path, path, payload))
    return ProjectState(root=str(root_path), contracts=contracts, warnings=warnings)


def _contract_summary(root: Path, path: Path, payload: dict[str, Any]) -> ContractSummary:
    relative = path.relative_to(root).as_posix()
    target = _mapping(payload.get("target"))
    source = _mapping(payload.get("source"))
    base = relative.removesuffix(".ingestion.yaml")
    sibling_root = root / base
    return ContractSummary(
        path=relative,
        layer=_layer(payload, target, relative),
        target_catalog=_string(target.get("catalog")),
        target_schema=_string(target.get("schema")),
        target_table=_string(target.get("table")),
        mode=_string(payload.get("mode")),
        source_connector=_string(source.get("connector") or source.get("type")),
        source_table=_string(source.get("table")),
        source_path=_string(source.get("path")),
        has_annotations=sibling_root.with_suffix(".annotations.yaml").exists(),
        has_operations=sibling_root.with_suffix(".operations.yaml").exists(),
    )


def _layer(payload: dict[str, Any], target: dict[str, Any], relative: str) -> Layer | None:
    candidates = [
        _string(payload.get("layer")),
        _string(target.get("schema")),
        relative.replace("\\", "/"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        lowered = candidate.lower()
        for layer in ("bronze", "silver", "gold"):
            if layer in lowered:
                return layer
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
