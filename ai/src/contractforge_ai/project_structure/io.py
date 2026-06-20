"""I/O helpers for ContractForge project-structure validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_mapping(path: Path) -> dict[str, Any]:
    """Load a JSON/YAML mapping from disk."""

    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a mapping object")
    return payload


def first_existing(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def iter_ingestion_files(root: Path) -> list[Path]:
    """Return user-authored ingestion files, excluding generated platform state."""

    ignored = {".git", ".databricks", ".terraform", "__pycache__", "dist", "build", ".venv", "venv"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored for part in path.parts):
            continue
        if path.name.endswith((".ingestion.yaml", ".ingestion.yml", ".ingestion.json")):
            files.append(path)
    return sorted(files)
